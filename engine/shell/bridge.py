"""pywebview js_api: the engine Api plus window controls; device events are pushed to the pages."""
from __future__ import annotations

import json
import logging
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
    def call(*args):
        try:
            return fn(*args)
        except ApiError as e:
            raise Exception(str(e)) from None
    call.__name__ = fn.__name__
    return call


class Bridge:
    def __init__(self, api: Api, host: WindowHost, autostart):
        self.api, self.host, self.autostart = api, host, autostart
        for name in API_METHODS:
            setattr(self, name, _plain(getattr(api, name)))
        api.subscribe(self.push)

    def push(self, name: str, payload: dict) -> None:
        try:
            msg = json.dumps({"name": name, "payload": payload})
            self.host.eval_all(f"window.__cavalryEmit && window.__cavalryEmit({msg})")
        except Exception:
            log.exception("could not deliver %s event to the UI", name)

    def set_app_settings(self, theme=None, autostart=None):
        out = _plain(self.api.set_app_settings)(theme, autostart)
        if autostart is not None:
            try:
                self.autostart.set(bool(autostart))
            except OSError as e:
                raise Exception(f"Couldn't change Start with Windows: {e}") from None
        return out

    def export_profile_dialog(self, name: str):
        path = self.host.save_dialog(name)
        if path:
            _plain(self.api.export_profile)(name, path)
        return path

    def import_profile_dialog(self):
        path = self.host.open_dialog()
        return _plain(self.api.import_profile)(path) if path else None

    def show_main(self): self.host.show_main()
    def hide_flyout(self): self.host.hide_flyout()
    def minimize(self): self.host.minimize()
    def quit(self): self.host.quit()
