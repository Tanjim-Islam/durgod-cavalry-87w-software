"""pywebview js_api: the engine Api plus window controls; device events are pushed to the pages."""
from __future__ import annotations

import json
import logging
import queue
import threading
from typing import Protocol

from ..api import Api, ApiError

log = logging.getLogger("cavalry")

API_METHODS = ("get_state", "set_lighting", "set_settings", "set_keep_lights_on", "remap_key", "reset_key",
               "reset_layer", "save_macro", "delete_macro", "clear_macros", "set_palette", "set_key_colors",
               "list_profiles", "save_profile", "apply_profile", "delete_profile", "list_backups",
               "restore_backup", "get_shortcuts", "get_app_settings")


class WindowHost(Protocol):
    def show_main(self) -> None: ...
    def hide_flyout(self) -> None: ...
    def minimize(self) -> None: ...
    def quit(self) -> None: ...
    def eval_all(self, js: str) -> None: ...
    def save_dialog(self, name: str) -> str | None: ...
    def open_dialog(self) -> str | None: ...


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


class Bridge:
    """Everything public here is callable from the page; keep internals underscored."""

    def __init__(self, api: Api, host: WindowHost, autostart):
        self._api, self._host, self._autostart = api, host, autostart
        self._events: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._closed = False
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
        path = self._host.open_dialog()
        return _plain(self._api.import_profile)(path, overwrite) if path else None

    def show_main(self): self._host.show_main()
    def hide_flyout(self): self._host.hide_flyout()
    def minimize(self): self._host.minimize()
    def quit(self): self._host.quit()
