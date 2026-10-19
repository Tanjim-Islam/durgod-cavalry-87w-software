"""Owns the keyboard: connection, safety rules, writes. DeviceManager is synchronous; Worker threads it."""
from __future__ import annotations

import queue
import threading
import time
from concurrent.futures import Future
from typing import Callable

from .codec.snapshot import Snapshot
from .links.base import Link, LinkError, NotSupported
from .protocol import MODEL_ID
from .store import Store


class NotReady(RuntimeError):
    pass


class VerifyError(LinkError):
    pass


def _merge(base: Snapshot, target: Snapshot, blocks: list[str]) -> Snapshot:
    out = base.copy()
    for name in blocks:
        if name.startswith("layer"):
            out.layers[int(name[-1])] = target.block(name)
        else:
            setattr(out, name, target.block(name))
    return out


class DeviceManager:
    def __init__(self, store: Store, detect: Callable[[], str | None],
                 open_link: Callable[[str], Link], clock=time.monotonic, stable_s: float = 5.0):
        self.store, self._detect, self._open, self._clock = store, detect, open_link, clock
        self.stable_s = stable_s
        self.kind: str | None = None
        self.link: Link | None = None
        self.snapshot: Snapshot | None = store.load_mirror()
        self.partial = False
        self.pending: Snapshot | None = None
        self._pending_blocks: list[str] = []
        self._since = 0.0
        self._subs: list[Callable[[str, dict], None]] = []

    # ---------- events
    def subscribe(self, cb: Callable[[str, dict], None]) -> None:
        self._subs.append(cb)

    def _emit(self, name: str, payload: dict | None = None) -> None:
        for cb in list(self._subs):
            try:
                cb(name, payload or {})
            except Exception:
                pass  # a bad subscriber must never break the device loop

    # ---------- connection
    def _drop(self) -> None:
        if self.link:
            try:
                self.link.close()
            except Exception:
                pass
        self.link = None
        self._since = self._clock()

    def _abort(self, link: Link | None, message: str) -> None:
        if link is not None:
            try:
                link.close()
            except Exception:
                pass
        self._drop()
        self._emit("error", {"message": message})

    def poll(self) -> None:
        kind = self._detect()
        if kind != self.kind:
            self._drop()
            self.kind = kind
            self._emit("link", {"kind": kind})
        if not kind:
            return
        if self.link is None:
            if self._clock() - self._since >= self.stable_s:
                self._connect()
            return
        try:
            cfg = self.link.read_config()
        except LinkError as e:
            self._drop()
            self._emit("error", {"message": f"Lost the keyboard: {e}"})
            return
        if self.snapshot and cfg != self.snapshot.config:
            snap = self.snapshot.copy()
            snap.config = cfg
            self.store.save_mirror(snap)
            self.snapshot = snap
            self._emit("state")

    def _connect(self) -> None:
        link = None
        try:
            link = self._open(self.kind)
            ident = link.identify()
        except Exception as e:
            self._abort(link, str(e))
            return
        if len(ident) < 6 or ident[5] != MODEL_ID:
            self._abort(link, f"Not a Cavalry 87W (model {ident.hex()})")
            return
        try:
            if link.kind == "wired":
                snap = link.read_all()
                if not self.store.has_factory():
                    self.store.save_backup(snap, factory=True, label="first connection")
                partial = False
            else:
                cfg = link.read_config()
                mirror = self.store.load_mirror()
                partial = mirror is None
                snap = None
                if mirror:
                    snap = mirror.copy()
                    snap.config = cfg
                    snap.validate()
            if snap:
                self.store.save_mirror(snap)
        except Exception as e:
            self._abort(link, str(e))
            return
        self.link, self.snapshot, self.partial = link, snap, partial
        if self.pending is not None and not partial:
            if not self._replay(snap):
                return
        self._emit("state")

    def _replay(self, base: Snapshot) -> bool:
        """Re-apply an interrupted batch once, on top of the freshly read state."""
        target, blocks = self.pending, self._pending_blocks
        self.pending, self._pending_blocks = None, []
        final = _merge(base, target, blocks)
        try:
            self._push(final, base.changed_blocks(final))
            self.store.save_mirror(final)
        except Exception:
            self._drop()
            self._emit("error", {"message": "Changes could not be applied after reconnecting"})
            return False
        self.snapshot = final.copy()
        return True

    # ---------- writes
    def _ready(self) -> None:
        if self.link is None:
            raise NotReady("Keyboard not connected (or still settling after a mode switch)")
        if self.partial or self.snapshot is None:
            raise NotReady("Connect the cable once so the app can read your keyboard")

    def apply(self, mutator: Callable[[Snapshot], Snapshot]) -> Snapshot:
        self._ready()
        if self.link.kind == "wired":
            base = self.link.read_all()
        else:
            base = self.snapshot.copy()
            base.config = self.link.read_config()
        target = mutator(base.copy())
        target.validate()
        blocks = base.changed_blocks(target)
        if not blocks:
            return base
        self.store.save_backup(base, label="before change")
        self._write(target, blocks)
        return target

    def restore(self, s: Snapshot) -> Snapshot:
        return self.apply(lambda _: s.copy())

    def _push(self, target: Snapshot, blocks: list[str]) -> None:
        for name in blocks:
            self.link.write_block(name, target.block(name))
        for name in blocks:
            if self.link.kind == "wired" or name == "config":
                if self.link.read_block(name) != target.block(name):
                    raise VerifyError(f"verify failed for {name}")

    def _write(self, target: Snapshot, blocks: list[str]) -> None:
        try:
            self._push(target, blocks)
        except VerifyError:
            self._emit("error", {"message": "Keyboard didn't accept the change"})
            raise
        except NotSupported as e:
            self._emit("error", {"message": str(e)})
            raise
        except LinkError as e:
            self.pending, self._pending_blocks = target, blocks
            self._drop()
            self._emit("error", {"message": f"Write interrupted, will retry when reconnected: {e}"})
            raise
        self.snapshot = target.copy()
        self.store.save_mirror(target)
        self._emit("state")


class Worker:
    """Runs DeviceManager on one thread: queued calls plus a poll every poll_s."""

    def __init__(self, manager: DeviceManager, poll_s: float = 1.0):
        self.m, self.poll_s = manager, poll_s
        self._q: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, name="cavalry-device", daemon=True)

    def start(self) -> None:
        self._t.start()

    def stop(self) -> None:
        self._stop.set()
        self._q.put(None)
        self._t.join(timeout=5)

    def call(self, fn, *args) -> Future:
        f: Future = Future()
        self._q.put((f, fn, args))
        return f

    def _run(self) -> None:
        next_poll = 0.0
        while not self._stop.is_set():
            timeout = max(0.0, next_poll - time.monotonic())
            try:
                item = self._q.get(timeout=timeout)
            except queue.Empty:
                item = "poll"
            if item is None:
                break
            if item == "poll":
                try:
                    self.m.poll()
                except Exception as e:  # never kill the worker
                    self.m._emit("error", {"message": str(e)})
                next_poll = time.monotonic() + self.poll_s
                continue
            f, fn, args = item
            try:
                f.set_result(fn(*args))
            except Exception as e:
                f.set_exception(e)
