"""Methods the web UI calls. Every method returns JSON-able data or raises ApiError."""
from __future__ import annotations

import functools
from pathlib import Path

from .codec.colors import (ColorError, decode_key_colors, decode_palette, encode_key_colors,
                           encode_palette)
from .codec.config import EFFECT_IDS, EFFECTS, Config, ConfigError
from .codec.keymap import (KEY_SLOTS, KeymapError, MacroRef, NoAction, action_from_dict,
                           action_to_dict, decode_layer, encode_layer, wired_unsafe)
from .codec.macro import (MacroError, decode_macros, encode_macros, macro_from_dict,
                          macro_to_dict)
from .codec.shortcuts import shortcut_table
from .codec.snapshot import Snapshot, SnapshotError
from .device import NotReady, VerifyError
from .links.base import LinkError, NotSupported, SizeGuardError
from .protocol import LAYER_COUNT, LAYER_SLOTS, PALETTE_GROUPS
from .store import Settings, Store, StoreError

_THEMES = ("dark", "light", "system")


class ApiError(Exception):
    pass


CABLE_WARNING = "Saved. This key works over 2.4G but won't send over the cable (cable supports up to F21)."


def _message(e: Exception) -> str:
    """User-readable text for any failure that can come out of the engine."""
    if isinstance(e, TimeoutError):  # also what Future.result raises; must precede OSError
        return "The keyboard did not respond in time. Check the connection and try again."
    if isinstance(e, VerifyError):
        return f"The keyboard did not accept the change ({e})"
    if isinstance(e, NotSupported):
        return f"Not supported on this connection: {e}"
    if isinstance(e, LinkError):
        return f"Keyboard communication failed: {e}"
    if isinstance(e, (NotReady, StoreError, SnapshotError, ConfigError, KeymapError, MacroError,
                      ColorError)):
        return str(e)
    if isinstance(e, SizeGuardError):
        return f"Refused to send malformed data: {e}"
    if isinstance(e, OSError):
        return f"File error: {e}"
    if isinstance(e, (KeyError, IndexError, ValueError, TypeError)):
        return f"Invalid request: {e}"
    return f"Unexpected error: {e}"


def _guarded(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ApiError:
            raise
        except Exception as e:
            raise ApiError(_message(e)) from e
    return wrapper


def _int(name: str, v, lo: int, hi: int) -> int:
    if type(v) is not int or not lo <= v <= hi:
        raise ApiError(f"{name} must be a whole number from {lo} to {hi}")
    return v


def _colors(name: str, v, n: int) -> list[tuple[int, int, int]]:
    if not isinstance(v, (list, tuple)) or len(v) != n:
        raise ApiError(f"{name} needs exactly {n} colors")
    out = []
    for c in v:
        if (not isinstance(c, (list, tuple)) or len(c) != 3
                or any(type(x) is not int or not 0 <= x <= 255 for x in c)):
            raise ApiError(f"{name}: each color must be [red, green, blue] with values 0..255")
        out.append((c[0], c[1], c[2]))
    return out


def _position(layer, slot) -> None:
    _int("layer", layer, 0, LAYER_COUNT - 1)
    _int("key slot", slot, 0, LAYER_SLOTS - 1)


def _check_index(index, count: int, what: str) -> None:
    if type(index) is not int or not 0 <= index < count:
        raise ApiError(f"No {what} number {index!r}")


class Api:
    TIMEOUT_S = 60

    def __init__(self, manager, worker, store: Store):
        self.m, self.w, self.store = manager, worker, store

    # ---------- helpers
    def _apply(self, mutator) -> dict:
        self.w.call(self.m.apply, mutator).result(timeout=self.TIMEOUT_S)
        return self.get_state()

    def _factory(self) -> Snapshot | None:
        return self.store.load_backup("factory") if self.store.has_factory() else None

    # ---------- state
    @_guarded
    def get_state(self) -> dict:
        s, m = self.m.snapshot, self.m
        out = {"connected": m.link is not None, "link": m.kind, "partial": m.partial,
               "effects": [{"id": i, "name": n} for i, n in EFFECTS],
               "key_names": {str(k): v for k, v in KEY_SLOTS.items()}}
        if s is None:
            return out
        c = Config(s.config)
        try:
            fields = {"brightness": c.brightness(), "speed": c.speed(), "color": c.color(),
                      "direction": c.direction()}
        except ConfigError:  # effect byte the app doesn't know: show it, don't guess the rest
            fields = dict.fromkeys(("brightness", "speed", "color", "direction"))
        out["lighting"] = {"effect": c.effect, **fields, "keep_lights_on": c.sleep == 0}
        out["settings"] = {"win_mac": c.win_mac, "sleep": c.sleep, "debounce": c.debounce}
        out["layers"] = [[action_to_dict(a) for a in decode_layer(x)] for x in s.layers]
        out["macros"] = [macro_to_dict(x) for x in decode_macros(s.macros)]
        out["key_colors"] = decode_key_colors(s.key_colors)
        out["palette"] = decode_palette(s.palette)
        return out

    # ---------- lighting and settings
    @_guarded
    def set_lighting(self, effect=None, brightness=None, speed=None, color=None, direction=None):
        if effect is not None and effect not in EFFECT_IDS:
            raise ApiError(f"Unknown lighting effect {effect!r}")
        if brightness is not None:
            _int("brightness", brightness, 0, 4)
        if speed is not None:
            _int("speed", speed, 0, 4)
        if color is not None:
            _int("color", color, 0, 7)
        if direction is not None and type(direction) is not bool:
            raise ApiError("direction must be true or false")

        def m(s):
            c = Config(s.config)
            if effect is not None:
                c.effect = effect
            if brightness is not None:
                c.set_brightness(brightness)
            if speed is not None:
                c.set_speed(speed)
            if color is not None:
                c.set_color(color)
            if direction is not None:
                c.set_direction(direction)
            s.config = c.to_bytes()
            return s
        return self._apply(m)

    @_guarded
    def set_settings(self, win_mac=None, sleep=None, debounce=None):
        if win_mac is not None and win_mac not in ("win", "mac"):
            raise ApiError("win_mac must be 'win' or 'mac'")
        if sleep is not None:
            _int("sleep", sleep, 0, 255)
        if debounce is not None:
            _int("debounce", debounce, 0, 4)

        def m(s):
            c = Config(s.config)
            if win_mac is not None:
                c.win_mac = win_mac
            if sleep is not None:
                c.sleep = sleep
            if debounce is not None:
                c.debounce = debounce
            s.config = c.to_bytes()
            return s
        return self._apply(m)

    @_guarded
    def set_keep_lights_on(self, on: bool):
        if type(on) is not bool:
            raise ApiError("on must be true or false")
        factory = self._factory()
        default = Config(factory.config).sleep if factory else 0x0C
        return self.set_settings(sleep=0 if on else (default or 0x0C))

    # ---------- keys
    def _set_slot(self, layer: int, slot: int, action):
        def m(s):
            acts = decode_layer(s.layers[layer])
            acts[slot] = action
            s.layers[layer] = encode_layer(acts)
            return s
        return self._apply(m)

    @_guarded
    def remap_key(self, layer: int, slot: int, action: dict):
        _position(layer, slot)
        a = action_from_dict(action)
        state = self._set_slot(layer, slot, a)
        if wired_unsafe(a):
            state["warning"] = CABLE_WARNING
        return state

    @_guarded
    def reset_key(self, layer: int, slot: int):
        _position(layer, slot)
        f = self._factory()
        if f is None:
            raise ApiError("No factory snapshot yet: connect the cable once")
        return self._set_slot(layer, slot, decode_layer(f.layers[layer])[slot])

    @_guarded
    def reset_layer(self, layer: int):
        _int("layer", layer, 0, LAYER_COUNT - 1)
        f = self._factory()
        if f is None:
            raise ApiError("No factory snapshot yet: connect the cable once")

        def m(s):
            s.layers[layer] = f.layers[layer]
            return s
        return self._apply(m)

    # ---------- macros
    @_guarded
    def save_macro(self, index, macro: dict) -> dict:
        if index is not None and (type(index) is not int or index < 0):
            raise ApiError(f"No macro number {index!r}")
        try:
            new = macro_from_dict(macro)
        except (MacroError, TypeError, KeyError) as e:
            raise ApiError(f"Invalid macro: {e}") from e
        unsafe = any(e.kind == "key" and e.code > 0x70 for e in new.events)
        result = {}

        def m(s):
            ms = decode_macros(s.macros)
            if index is None:
                ms.append(new)
                result["i"] = len(ms) - 1
            else:
                _check_index(index, len(ms), "macro")
                ms[index] = new
                result["i"] = index
            s.macros = encode_macros(ms)
            return s
        self._apply(m)
        return {"index": result["i"], "warning": CABLE_WARNING if unsafe else None}

    @_guarded
    def delete_macro(self, index: int):
        if type(index) is not int or index < 0:
            raise ApiError(f"No macro number {index!r}")

        def m(s):
            ms = decode_macros(s.macros)
            _check_index(index, len(ms), "macro")
            del ms[index]
            s.macros = encode_macros(ms)
            for li in range(LAYER_COUNT):
                fixed = []
                for a in decode_layer(s.layers[li]):
                    if isinstance(a, MacroRef) and a.index == index:
                        fixed.append(NoAction())
                    elif isinstance(a, MacroRef) and a.index > index:
                        fixed.append(MacroRef(a.index - 1, a.mode, a.count))
                    else:
                        fixed.append(a)
                s.layers[li] = encode_layer(fixed)
            return s
        return self._apply(m)

    # ---------- colors
    @_guarded
    def set_palette(self, group: int, colors: list):
        _int("palette group", group, 0, PALETTE_GROUPS - 1)
        new = _colors("palette group", colors, 7)

        def m(s):
            p = decode_palette(s.palette)
            p[group] = new
            s.palette = encode_palette(p)
            return s
        return self._apply(m)

    @_guarded
    def set_key_colors(self, colors: list):
        new = _colors("key colors", colors, LAYER_SLOTS)

        def m(s):
            s.key_colors = encode_key_colors(new)
            return s
        return self._apply(m)

    # ---------- profiles and backups
    @_guarded
    def list_profiles(self):
        return self.store.list_profiles()

    @_guarded
    def save_profile(self, name: str):
        if self.m.snapshot is None:
            raise ApiError("Nothing to save yet: connect the keyboard")
        self.store.save_profile(name, self.m.snapshot)
        return self.list_profiles()

    @_guarded
    def apply_profile(self, name: str):
        s = self.store.load_profile(name)
        return self._apply(lambda _: s.copy())

    @_guarded
    def delete_profile(self, name: str):
        self.store.delete_profile(name)
        return self.list_profiles()

    @_guarded
    def export_profile(self, name: str, path: str):
        self.store.export_profile(name, Path(path))

    @_guarded
    def import_profile(self, path: str):
        try:
            return self.store.import_profile(Path(path))
        except (StoreError, KeyError, ValueError) as e:
            raise ApiError(f"Not a valid profile file: {e}") from e

    @_guarded
    def list_backups(self):
        return [b.model_dump(mode="json") for b in self.store.list_backups()]

    @_guarded
    def restore_backup(self, name: str):
        s = self.store.load_backup(name)
        return self._apply(lambda _: s.copy())

    # ---------- shortcuts and app settings
    @_guarded
    def get_shortcuts(self):
        s = self.m.snapshot or self._factory()
        if s is None:
            raise ApiError("Connect the keyboard once to read its shortcuts")
        return shortcut_table(decode_layer(s.layers[1]))

    @_guarded
    def get_app_settings(self):
        return self.store.load_settings().model_dump()

    @_guarded
    def set_app_settings(self, theme=None, autostart=None):
        if theme is not None and theme not in _THEMES:
            raise ApiError(f"theme must be one of {', '.join(_THEMES)}")
        if autostart is not None and type(autostart) is not bool:
            raise ApiError("autostart must be true or false")
        cur = self.store.load_settings()
        new = Settings(theme=cur.theme if theme is None else theme,
                       autostart=cur.autostart if autostart is None else autostart)
        self.store.save_settings(new)
        return new.model_dump()
