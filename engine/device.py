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
from .store import Store, StoreError


class NotReady(RuntimeError):
    pass


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
        self._since = 0.0
        self._subs: list[Callable[[str, dict], None]] = []

    # ---------- events
    def subscribe(self, cb: Callable[[str, dict], None]) -> None:
        self._subs.append(cb)

    def _emit(self, name: str, payload: dict | None = None) -> None:
        for cb in self._subs:
            cb(name, payload or {})

    # ---------- connection
    def _drop(self) -> None:
        if self.link:
            try:
                self.link.close()
            except Exception:
                pass
        self.link = None
        self._since = self._clock()

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
            self.snapshot.config = cfg
            self.store.save_mirror(self.snapshot)
            self._emit("state")

    def _connect(self) -> None:
        try:
            link = self._open(self.kind)
            ident = link.identify()
        except LinkError as e:
            self._since = self._clock()
            self._emit("error", {"message": str(e)})
            return
        if len(ident) < 6 or ident[5] != MODEL_ID:
            link.close()
            self._since = self._clock()
            self._emit("error", {"message": f"Not a Cavalry 87W (model {ident.hex()})"})
            return
        self.link = link
        try:
            if link.kind == "wired":
                snap = link.read_all()
                if not self.store.has_factory():
                    self.store.save_backup(snap, factory=True, label="first connection")
                self.partial = False
            else:
                cfg = link.read_config()
                mirror = self.store.load_mirror()
                self.partial = mirror is None
                snap = mirror
                if snap:
                    snap.config = cfg
            self.snapshot = snap
            if snap:
                self.store.save_mirror(snap)
            if self.pending is not None and not self.partial:
                self.store.save_backup(snap, label="before retry")
                self._write(self.pending, snap)
        except (OSError, StoreError) as e:
            self._drop()
            self._emit("error", {"message": str(e)})
            return
        self._emit("state")

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
        if not base.changed_blocks(target):
            return base
        self.store.save_backup(base, label="before change")
        self._write(target, base)
        return target

    def restore(self, s: Snapshot) -> Snapshot:
        return self.apply(lambda _: s.copy())

    def _write(self, target: Snapshot, base: Snapshot | None = None) -> None:
        base = base or self.snapshot
        blocks = base.changed_blocks(target) if base else []
        self.pending = target
        try:
            for name in blocks:
                self.link.write_block(name, target.block(name))
            for name in blocks:
                if self.link.kind == "wired" or name == "config":
                    if self.link.read_block(name) != target.block(name):
                        raise LinkError(f"verify failed for {name}")
        except (LinkError, NotSupported) as e:
            self._drop()
            self._emit("error", {"message": f"Write interrupted, will retry when reconnected: {e}"})
            raise
        except Exception:
            self.pending = None
            raise
        self.pending = None
        self.snapshot = target
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
