"""Methods the web UI calls. Every method returns JSON-able data or raises ApiError.

Events: Api.subscribe(cb) makes the device thread call cb(name, payload) for each of these.
- "state", {}: keyboard state or connection changed (connect, drop, write, Fn change); call get_state.
- "link", {"kind": "wired" | "radio" | None}: the detected link changed.
- "link", {"kind": "radio", "online": False}: dongle present but the keyboard is asleep or off.
  A status, not an error.
- "mirror_mismatch", {"blocks": [...]}: on cable connect, these blocks differed from the local
  copy (changed by something else while the app was away).
- "error", {"message": str}: a background failure (connecting, polling, replaying an interrupted
  write, saving local files).
A failing Api call is reported only by raising ApiError, never by an "error" event.
"""
from __future__ import annotations

import functools
import logging
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
from .store import ProfileExists, Settings, Store, StoreError

log = logging.getLogger("cavalry")

_THEMES = ("dark", "light", "system")
_EXPECTED = (TimeoutError, LinkError, NotReady, StoreError, SnapshotError, ConfigError, KeymapError,
             MacroError, ColorError, SizeGuardError, OSError)


class ApiError(Exception):
    pass


CABLE_WARNING = "Saved. This key works over 2.4G but won't send over the cable (cable supports up to F21)."


def _message(e: Exception) -> str:
    """User-readable text for any failure that can come out of the engine."""
    if isinstance(e, TimeoutError):  # also what Future.result raises; must precede OSError
        return "The keyboard is busy; the change may still apply. Refresh before retrying."
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
            if not isinstance(e, _EXPECTED):
                log.exception("unexpected error in %s", fn.__name__)
            raise ApiError(_message(e)) from e
    return wrapper


def _warn(d: dict, msg: str | None) -> dict:
    if msg:
        d["warning"] = f"{d['warning']} {msg}" if d.get("warning") else msg
    return d


def _macros(raw: bytes) -> list:
    try:
        return decode_macros(raw)
    except MacroError as e:
        raise ApiError(f"The keyboard's macro memory can't be read ({e}). "
                       "Clear all macros (clear_macros) to start fresh.") from e


def _lighting(c: Config) -> dict:
    try:
        fields = {"brightness": c.brightness(), "speed": c.speed(), "color": c.color(),
                  "direction": c.direction()}
    except ConfigError:  # effect byte the app doesn't know: show it, don't guess the rest
        fields = dict.fromkeys(("brightness", "speed", "color", "direction"))
    return {"effect": c.effect, **fields, "keep_lights_on": c.sleep == 0}


def _settings(c: Config) -> dict:
    return {"win_mac": c.win_mac, "sleep": c.sleep, "debounce": c.debounce}


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
        def run():
            self.m.apply(mutator)
            return self.m.last_warning
        warning = self.w.call(run).result(timeout=self.TIMEOUT_S)
        try:  # the keyboard is written by now: never report this call as failed
            state = self.get_state()
        except Exception as e:
            log.exception("state refresh after a write failed")
            return {"warning": f"Saved to the keyboard, but the view couldn't refresh ({e}). "
                               "Refresh to see it."}
        return _warn(state, warning)

    @_guarded
    def subscribe(self, cb) -> None:
        """cb(name, payload) for every device event; see the module docstring."""
        self.m.subscribe(cb)

    def _factory(self) -> Snapshot | None:
        return self.store.load_backup("factory") if self.store.has_factory() else None

    # ---------- state
    @_guarded
    def get_state(self) -> dict:
        s, m = self.m.snapshot, self.m
        out = {"connected": m.link is not None, "link": m.kind, "partial": m.partial,
               "asleep": m.asleep,
               "effects": [{"id": i, "name": n} for i, n in EFFECTS],
               "key_names": {str(k): v for k, v in KEY_SLOTS.items()}}
        if s is None:
            return out

        def section(name: str, fn) -> None:
            """One unreadable block must not hide the others."""
            try:
                out[name] = fn()
            except Exception as e:
                log.warning("cannot decode %s: %s", name, e)
                out[name] = None
                out[f"{name}_error"] = f"Couldn't read {name.replace('_', ' ')}: {e}"

        section("lighting", lambda: _lighting(Config(s.config)))
        section("settings", lambda: _settings(Config(s.config)))
        section("layers", lambda: [[action_to_dict(a) for a in decode_layer(x)] for x in s.layers])
        section("macros", lambda: [macro_to_dict(x) for x in decode_macros(s.macros)])
        section("key_colors", lambda: decode_key_colors(s.key_colors))
        section("palette", lambda: decode_palette(s.palette))
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
    def _set_slot(self, layer: int, slot: int, action, check_macro: bool = False):
        def m(s):
            if check_macro and isinstance(action, MacroRef):
                count = len(_macros(s.macros))
                if action.index >= count:
                    raise ApiError(f"No macro number {action.index} (the keyboard has {count})")
            acts = decode_layer(s.layers[layer])
            acts[slot] = action
            s.layers[layer] = encode_layer(acts)
            return s
        return self._apply(m)

    @_guarded
    def remap_key(self, layer: int, slot: int, action: dict):
        _position(layer, slot)
        a = action_from_dict(action)
        state = self._set_slot(layer, slot, a, check_macro=True)
        return _warn(state, CABLE_WARNING if wired_unsafe(a) else None)

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
            ms = _macros(s.macros)
            if index is None:
                ms.append(new)
                result["i"] = len(ms) - 1
            else:
                _check_index(index, len(ms), "macro")
                ms[index] = new
                result["i"] = index
            s.macros = encode_macros(ms)
            return s
        state = self._apply(m)
        warning = _warn(_warn({}, state.get("warning")), CABLE_WARNING if unsafe else None)
        return {"index": result["i"], "warning": warning.get("warning")}

    @_guarded
    def delete_macro(self, index: int):
        if type(index) is not int or index < 0:
            raise ApiError(f"No macro number {index!r}")

        def m(s):
            ms = _macros(s.macros)
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

    @_guarded
    def clear_macros(self):
        """Erase every macro (also unreadable ones) and unbind keys that pointed to one."""
        def m(s):
            s.macros = encode_macros([])
            for li in range(LAYER_COUNT):
                acts = decode_layer(s.layers[li])
                if any(isinstance(a, MacroRef) for a in acts):
                    s.layers[li] = encode_layer(
                        [NoAction() if isinstance(a, MacroRef) else a for a in acts])
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
    def rename_profile(self, old: str, new: str):
        self.store.rename_profile(old, new)
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
    def import_profile(self, path: str, overwrite: bool = False):
        if type(overwrite) is not bool:
            raise ApiError("overwrite must be true or false")
        try:
            return self.store.import_profile(Path(path), overwrite=overwrite)
        except ProfileExists as e:
            raise ApiError(f"Not imported: {e}. Import again with overwrite to replace it.") from e
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
