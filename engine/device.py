"""Owns the keyboard: connection, safety rules, writes. DeviceManager is synchronous; Worker threads it."""
from __future__ import annotations

import logging
import queue
import threading
import time
from concurrent.futures import Future
from typing import Callable

from .codec.config import OFF_LINK
from .codec.snapshot import Snapshot
from .links.base import Link, LinkError, NotSupported
from .protocol import (CONFIG_SIZE, KEY_COLORS_SIZE, LAYER_COUNT, LAYER_SIZE, MACRO_SIZE, MODEL_ID,
                       PALETTE_SIZE)
from .store import Store, StoreError

log = logging.getLogger("cavalry")

MIRROR_WARNING = "Saved to keyboard, but the local copy couldn't be saved"
MIRROR_ERROR = "Couldn't save the local copy of your keyboard settings"
CONFIG_BACKUP_EVERY_S = 60.0
DRAIN_TIMEOUT_S = 65.0  # longer than Api.TIMEOUT_S, so a call the UI is still waiting on can finish


NEEDS_CABLE = ("Plug in the cable and press Fn + PrtSc (wired mode) once, so the app can read your keys, "
               "macros and colors. Lighting and settings already work over 2.4G.")


class NotReady(RuntimeError):
    pass


class VerifyError(LinkError):
    pass


class ShuttingDown(NotReady):
    pass


def _merge(base: Snapshot, target: Snapshot, blocks: list[str]) -> Snapshot:
    out = base.copy()
    for name in blocks:
        if name.startswith("layer"):
            out.layers[int(name[-1])] = target.block(name)
        else:
            setattr(out, name, target.block(name))
    return out


def _keep_link_byte(base: Snapshot, target: Snapshot) -> Snapshot:
    """Config 0x0E says which link is up; it belongs to the keyboard, never to saved data."""
    if target.config[OFF_LINK] != base.config[OFF_LINK]:
        c = bytearray(target.config)
        c[OFF_LINK] = base.config[OFF_LINK]
        target.config = bytes(c)
    return target


class DeviceManager:
    def __init__(self, store: Store, detect: Callable[[], str | None],
                 open_link: Callable[[str], Link], clock=time.monotonic, stable_s: float = 5.0):
        self.store, self._detect, self._open, self._clock = store, detect, open_link, clock
        self.stable_s = stable_s
        self.kind: str | None = None
        self.link: Link | None = None
        try:
            self.snapshot: Snapshot | None = store.load_mirror_or_none()
        except StoreError as e:
            log.warning("could not read mirror at startup: %s", e)
            self.snapshot = None
        self.partial = False
        self.radio_config: bytes | None = None   # 2.4G before any cable read: the only block it can read
        self.asleep = False
        self.last_warning: str | None = None
        self.pending: Snapshot | None = None
        self._pending_blocks: list[str] = []
        self._since = 0.0
        self._mirror_failed = False
        self._last_config_backup: float | None = None
        self._subs: list[Callable[[str, dict], None]] = []

    # ---------- events
    def subscribe(self, cb: Callable[[str, dict], None]) -> None:
        self._subs.append(cb)

    def _emit(self, name: str, payload: dict | None = None) -> None:
        for cb in list(self._subs):
            try:
                cb(name, payload or {})
            except Exception:  # a bad subscriber must never break the device loop
                log.exception("event subscriber failed on %r", name)

    # ---------- connection
    @staticmethod
    def _close(link: Link) -> None:
        try:
            link.close()
        except Exception:
            pass

    def _drop(self) -> None:
        had = self.link is not None
        if self.link:
            self._close(self.link)
        self.link = None
        self.radio_config = None
        self._since = self._clock()
        if had:
            self._emit("state")

    def _abort(self, link: Link | None, message: str) -> None:
        if link is not None:
            self._close(link)
        self._drop()
        self._emit("error", {"message": message})

    def _went_to_sleep(self) -> None:
        """2.4G dongle present but the keyboard is asleep or off: a status, not an error."""
        self._drop()
        if not self.asleep:
            self.asleep = True
            self._emit("link", {"kind": "radio", "online": False})

    def _save_mirror(self, snap: Snapshot) -> bool:
        try:
            self.store.save_mirror(snap)
        except Exception as e:
            log.warning("could not save mirror: %s", e)
            return False
        self._mirror_failed = False
        return True

    def _persist(self, snap: Snapshot, message: str) -> None:
        """Background mirror save: one error event per run of failures."""
        if not self._save_mirror(snap) and not self._mirror_failed:
            self._mirror_failed = True
            self._emit("error", {"message": message})

    def poll(self) -> None:
        kind = self._detect()
        if kind != self.kind:
            self.kind, self.asleep = kind, False
            self._drop()
            self._emit("link", {"kind": kind})
        if not kind:
            return
        if self.link is None:
            if self._clock() - self._since >= self.stable_s:
                self._connect()
            return
        try:
            if self.link.kind == "radio" and not self.link.online():
                self._went_to_sleep()
                return
            cfg = self.link.read_config()
        except LinkError as e:
            self._drop()
            self._emit("error", {"message": f"Lost the keyboard: {e}"})
            return
        if self.snapshot and cfg != self.snapshot.config:
            snap = self.snapshot.copy()
            snap.config = cfg
            self.snapshot = snap
            self._persist(snap, MIRROR_ERROR)
            self._emit("state")

    def _capture_factory(self, link: Link, first: Snapshot) -> str | None:
        """Save the factory snapshot from two identical reads; returns why not, or None."""
        if link.read_all() != first:
            return "The keyboard gave two different readings, so no factory snapshot was saved yet"
        try:
            self.store.save_backup(first, factory=True, label="first connection")
        except Exception as e:
            return f"Couldn't save the factory snapshot: {e}"
        return None

    def _connect(self) -> None:
        link = None
        try:
            link = self._open(self.kind)
            if link.kind == "radio" and not link.online():
                self._close(link)
                self._went_to_sleep()
                return
            ident = link.identify()
        except Exception as e:
            self._abort(link, str(e))
            return
        self.asleep = False
        if len(ident) < 6 or ident[5] != MODEL_ID:
            self._abort(link, f"Not a Cavalry 87W (model {ident.hex()})")
            return
        factory_problem = None
        try:
            cfg = None
            if link.kind == "wired":
                snap = link.read_all()
                if not self.store.has_factory():
                    factory_problem = self._capture_factory(link, snap)
                prev = self.store.load_mirror_or_none()
                partial = False
            else:
                cfg = link.read_config()
                mirror = self.store.load_mirror_or_none()
                partial = mirror is None
                snap = None
                if mirror:
                    snap = mirror.copy()
                    snap.config = cfg
                    snap.validate()
        except Exception as e:
            self._abort(link, str(e))
            return
        if factory_problem:
            self._emit("error", {"message": f"{factory_problem}. Will retry on the next connection."})
        if link.kind == "wired":
            changed = [b for b in prev.changed_blocks(snap) if b != "config"] if prev else []
            if changed:
                self._emit("mirror_mismatch", {"blocks": changed})
        if snap:
            self._persist(snap, MIRROR_ERROR)
        self.link, self.snapshot, self.partial = link, snap, partial
        self.radio_config = cfg if partial else None
        if self.pending is not None and not partial:
            if not self._replay(snap):
                return
        self._emit("state")

    def _replay(self, base: Snapshot) -> bool:
        """Re-apply an interrupted batch once, on top of the freshly read state."""
        target, blocks = self.pending, self._pending_blocks
        self.pending, self._pending_blocks = None, []
        final = _keep_link_byte(base, _merge(base, target, blocks))
        try:
            self._push(final, base.changed_blocks(final))
        except Exception as e:
            log.warning("replay failed: %s", e)
            self._emit("error", {"message": "Changes could not be applied after reconnecting"})
            self._drop()
            return False
        self.snapshot = final.copy()
        self._persist(final, MIRROR_WARNING)
        return True

    # ---------- writes
    def _ready(self) -> None:
        if self.link is None:
            raise NotReady("Keyboard not connected (or still settling after a mode switch)")
        if self.partial or self.snapshot is None:
            raise NotReady(NEEDS_CABLE)

    def apply(self, mutator: Callable[[Snapshot], Snapshot]) -> Snapshot | None:
        """Write mutator(current state). Failures raise; they are never sent as error events."""
        if self.link is not None and self.link.kind == "radio" and (self.partial or not self.store.has_factory()):
            return self._apply_config_only(mutator)
        self._ready()
        self.last_warning = None
        if self.link.kind == "wired":
            base = self.link.read_all()
            if not self.store.has_factory():
                problem = self._capture_factory(self.link, base)
                if problem:
                    raise NotReady(problem)
        else:
            if not self.store.has_factory():
                raise NotReady("No factory snapshot yet: connect the cable once")
            base = self.snapshot.copy()
            base.config = self.link.read_config()
        target = _keep_link_byte(base, mutator(base.copy()))
        target.validate()
        blocks = base.changed_blocks(target)
        if not blocks:
            return base
        self._backup(base, blocks)
        self._write(target, blocks)
        return target

    def _apply_config_only(self, mutator: Callable[[Snapshot], Snapshot]) -> None:
        """2.4G before the first cable read: only config (lighting, sleep, Win/Mac, debounce) can be
        read back, so only edits that touch nothing else are allowed."""
        cfg = self.link.read_config()
        probe = Snapshot(cfg, [bytes(LAYER_SIZE) for _ in range(LAYER_COUNT)], bytes(MACRO_SIZE),
                         bytes(KEY_COLORS_SIZE), bytes(PALETTE_SIZE))
        target = _keep_link_byte(probe, mutator(probe.copy()))
        if len(target.config) != CONFIG_SIZE:
            raise NotReady(NEEDS_CABLE)
        blocks = probe.changed_blocks(target)
        if any(b != "config" for b in blocks):
            raise NotReady(NEEDS_CABLE)
        if blocks:
            try:
                self._push(target, ["config"])
            except LinkError as e:
                self._drop()
                raise LinkError(f"Write interrupted: {e}") from e
        if self.snapshot is not None:
            self.snapshot.config = target.config
            self._persist(self.snapshot, MIRROR_ERROR)
        else:
            self.radio_config = target.config
        self._emit("state")
        return None

    def restore(self, s: Snapshot) -> Snapshot:
        return self.apply(lambda _: s.copy())

    def _backup(self, base: Snapshot, blocks: list[str]) -> None:
        """Rolling backup, coalesced so config tweaks can't push out older block backups."""
        if base == self.store.latest_backup():
            return
        now = self._clock()
        if blocks == ["config"]:
            last = self._last_config_backup
            if last is not None and now - last < CONFIG_BACKUP_EVERY_S:
                return
        self.store.save_backup(base, label="before change")
        if blocks == ["config"]:
            self._last_config_backup = now

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
        except (VerifyError, NotSupported):
            raise
        except LinkError as e:
            self.pending, self._pending_blocks = target, blocks
            self._drop()
            raise LinkError(f"Write interrupted, will retry when reconnected: {e}") from e
        self.snapshot = target.copy()
        if not self._save_mirror(target):
            self.last_warning = MIRROR_WARNING
        self._emit("state")


class Worker:
    """Runs DeviceManager on one thread: queued calls plus a poll every poll_s.

    Shutdown drains: calls already queued still run, new ones are refused."""

    def __init__(self, manager: DeviceManager, poll_s: float = 1.0):
        self.m, self.poll_s = manager, poll_s
        self._q: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._closed = False
        self._t = threading.Thread(target=self._run, name="cavalry-device", daemon=True)

    def start(self) -> None:
        self._t.start()

    def close(self) -> None:
        """Refuse new calls; the thread exits once the queued ones are done."""
        with self._lock:
            if not self._closed:
                self._closed = True
                self._q.put(None)

    def stop(self, timeout: float = DRAIN_TIMEOUT_S) -> None:
        self.close()
        if not self._t.is_alive():
            return
        self._t.join(timeout=timeout)
        if self._t.is_alive():
            log.warning("keyboard worker still writing after %.0f s; exiting anyway", timeout)

    def call(self, fn, *args) -> Future:
        f: Future = Future()
        with self._lock:
            if not self._closed:
                self._q.put((f, fn, args))
                return f
        f.set_exception(ShuttingDown("The app is closing"))
        return f

    def _run(self) -> None:
        next_poll = 0.0
        while True:
            closing = self._closed
            timeout = None if closing else max(0.0, next_poll - time.monotonic())
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
                    log.exception("device poll failed")
                    self.m._emit("error", {"message": str(e)})
                next_poll = time.monotonic() + self.poll_s
                continue
            f, fn, args = item
            try:
                f.set_result(fn(*args))
            except Exception as e:
                f.set_exception(e)
