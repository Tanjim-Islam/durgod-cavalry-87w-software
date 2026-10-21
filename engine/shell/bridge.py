"""pywebview js_api: the engine Api plus window controls; device events are pushed to the pages."""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from concurrent.futures import Future
from typing import Callable, Protocol

from ..api import Api, ApiError
from ..store import ProfileExists
from .recorder import KeyboardHook, Recorder

log = logging.getLogger("cavalry")

API_METHODS = ("get_state", "set_lighting", "set_settings", "set_keep_lights_on", "remap_key", "reset_key",
               "reset_layer", "save_macro", "delete_macro", "clear_macros", "set_palette", "set_key_colors",
               "list_profiles", "save_profile", "rename_profile", "apply_profile", "delete_profile", "list_backups",
               "restore_backup", "get_shortcuts", "get_app_settings", "retry_connect", "dismiss_notice")


class WindowHost(Protocol):
    def show_main(self) -> None: ...
    def hide_main(self) -> None: ...
    def hide_flyout(self) -> None: ...
    def minimize(self) -> None: ...
    def toggle_maximize(self) -> None: ...
    def open_logs(self) -> None: ...
    def quit(self) -> None: ...
    def eval_all(self, js: str) -> None: ...
    def save_dialog(self, name: str) -> str | None: ...
    def open_dialog(self) -> str | None: ...


class _Lane:
    """One daemon thread per window, so a hung page only blocks its own lane."""

    def __init__(self, name: str):
        self._q: queue.Queue = queue.Queue()
        self.last: Future | None = None
        threading.Thread(target=self._run, name=f"cavalry-eval-{name}", daemon=True).start()

    def submit(self, fn, js: str) -> Future:
        self.last = Future()
        self._q.put((self.last, fn, js))
        return self.last

    def _run(self) -> None:
        while True:
            f, fn, js = self._q.get()
            try:
                f.set_result(fn(js))
            except Exception as e:
                f.set_exception(e)


class Courier:
    """Delivers one script to several windows, waiting at most `timeout` s; a still-busy window is skipped."""

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self._lanes: dict[str, _Lane] = {}

    def send(self, targets: dict[str, Callable[[str], object]], js: str) -> None:
        sent = {}
        for name, fn in targets.items():
            lane = self._lanes.get(name) or self._lanes.setdefault(name, _Lane(name))
            if lane.last is not None and not lane.last.done():
                log.warning("%s is not responding; skipped an event", name)
                continue
            sent[name] = lane.submit(fn, js)
        deadline = time.monotonic() + self.timeout
        for name, f in sent.items():
            try:
                f.result(timeout=max(0.0, deadline - time.monotonic()))
            except TimeoutError:
                log.warning("%s did not take an event within %.0f s", name, self.timeout)
            except Exception:
                log.exception("could not deliver an event to %s", name)


def _plain(fn):
    """pywebview shows the exception text; strip the ApiError type so the UI gets the message only."""
    def call(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ApiError as e:
            raise Exception(str(e)) from None
    call.__name__ = fn.__name__
    return call


def _hidden(fn):
    """pywebview exposes every public attribute to JS unless it is marked not serializable."""
    fn._serializable = False
    return fn


CLOSE_KEYS = {0x3D, 0xE2, 0xE6}   # F4, Left Alt, Right Alt


def _drop_close_keys(events: list) -> None:
    """A close by Alt+F4 ends up at the end of the recording: trim that chord so the macro can't close windows.
    Only a complete trailing chord is dropped, so no key is left held down."""
    i = len(events)
    while i and events[i - 1]["code"] in CLOSE_KEYS:
        i -= 1
    tail = events[i:]
    balanced = all(sum(1 if e["release"] else -1 for e in tail if e["code"] == c) == 0 for c in CLOSE_KEYS)
    if balanced and any(e["code"] == 0x3D and not e["release"] for e in tail):
        del events[i:]


class Bridge:
    """Everything public here is callable from the page; keep internals underscored."""

    def __init__(self, api: Api, host: WindowHost, autostart):
        self._api, self._host, self._autostart = api, host, autostart
        self._events: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._closed = False
        self._clash_path: str | None = None
        self._recording = None          # (Recorder, KeyboardHook, Timer) while a recording runs
        self._rec_done: dict | None = None  # result of a recording that timed out, for the next stop call
        self._rec_lock = threading.Lock()
        self._rec_timeout_s = 600.0
        for name in API_METHODS:
            setattr(self, name, _plain(getattr(api, name)))
        api.subscribe(self.push)

    @_hidden
    def start(self) -> None:
        with self._lock:
            if self._thread is None and not self._closed:
                self._thread = threading.Thread(target=self._dispatch, name="cavalry-events", daemon=True)
                self._thread.start()

    @_hidden
    def stop(self) -> None:
        self._stop_recording()
        with self._lock:
            self._closed = True
            t = self._thread
        self._events.put(None)
        if t is not None:
            t.join(timeout=5)

    @_hidden
    def push(self, name: str, payload: dict) -> None:
        """Called on the device thread: only enqueue, never block or raise."""
        try:
            if self._closed:
                return
            msg = json.dumps({"name": name, "payload": payload})
            self._events.put(f"window.__cavalryEmit && window.__cavalryEmit({msg})")
            self.start()
        except Exception:
            log.exception("could not queue %s event for the UI", name)

    def _dispatch(self) -> None:
        while (js := self._events.get()) is not None:
            try:
                self._host.eval_all(js)
            except Exception:
                log.exception("could not deliver an event to the UI")

    def set_app_settings(self, theme=None, autostart=None):
        previous = None
        if autostart is not None:
            try:
                previous = self._autostart.enabled()
                self._autostart.set(bool(autostart))
            except OSError as e:
                raise Exception(f"Couldn't change Start with Windows: {e}") from None
        try:
            return _plain(self._api.set_app_settings)(theme, autostart)
        except Exception:
            if previous is not None:
                try:
                    self._autostart.set(previous)
                except OSError:
                    log.exception("could not restore the Start with Windows entry")
            raise

    def export_profile_dialog(self, name: str):
        path = self._host.save_dialog(name)
        if path:
            _plain(self._api.export_profile)(name, path)
        return path

    def import_profile_dialog(self, overwrite: bool = False):
        # "Replace" after a name clash imports the file already picked instead of asking again.
        path = self._clash_path if overwrite and self._clash_path else self._host.open_dialog()
        self._clash_path = None
        if not path:
            return None
        try:
            return self._api.import_profile(path, overwrite)
        except ApiError as e:
            if not overwrite and isinstance(e.__cause__, ProfileExists):
                self._clash_path = path
            raise Exception(str(e)) from None

    def record_macro_start(self):
        """Start recording; an active recording (e.g. from a page that went away) is replaced."""
        with self._rec_lock:
            self._end_recording()
            self._rec_done = None
            rec = Recorder()
            rec.start()
            hook = KeyboardHook(rec.on_key)
            try:
                hook.start()
            except Exception as e:
                raise Exception(str(e)) from None
            timer = threading.Timer(self._rec_timeout_s, self._auto_stop)
            timer.daemon = True
            self._recording = (rec, hook, timer)
            timer.start()

    def record_macro_stop(self):
        with self._rec_lock:
            if not self._recording:
                done, self._rec_done = self._rec_done, None
                if done is None:
                    raise Exception("Not recording")
                return done
            rec, hook, timer = self._recording
            self._recording = None
            timer.cancel()
            hook.stop()
            return rec.stop()

    def _auto_stop(self) -> None:
        """Safety net: remove the hook after the timeout and keep the events for the next stop call."""
        with self._rec_lock:
            if not self._recording or self._recording[2] is not threading.current_thread():
                return
            self._park_recording()
            log.warning("macro recording stopped after %.0f s", self._rec_timeout_s)

    def _park_recording(self) -> None:
        """Caller holds _rec_lock: end an active recording, keep its events for the next stop call."""
        rec = self._recording[0]
        self._end_recording()
        self._rec_done = rec.stop()
        self.push("recording_stopped", {})

    @_hidden
    def pause_recording(self) -> None:
        """The window went to the tray: stop listening to keys but keep what was recorded."""
        with self._rec_lock:
            if self._recording:
                self._park_recording()
                _drop_close_keys(self._rec_done["events"])

    def _end_recording(self) -> None:
        """Caller holds _rec_lock: drop an active recording, its hook and its timer."""
        cur, self._recording = self._recording, None
        if not cur:
            return
        cur[2].cancel()
        try:
            cur[1].stop()
        except Exception:
            log.exception("could not stop the keyboard recorder")

    def _stop_recording(self) -> None:
        """Shutdown only: drop an active recording and its hook."""
        with self._rec_lock:
            self._end_recording()

    def show_main(self): self._host.show_main()
    def hide_main(self): self._host.hide_main()
    def hide_flyout(self): self._host.hide_flyout()
    def minimize(self): self._host.minimize()
    def toggle_maximize(self): self._host.toggle_maximize()
    def open_logs(self): self._host.open_logs()
    def quit(self): self._host.quit()
