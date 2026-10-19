"""Key layer entries: 4 bytes per slot, 126 slots per layer (cmd 0x83/0x03 wired, 0x01 radio)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from ..protocol import LAYER_SIZE, LAYER_SLOTS, NKRO_MAX_HID

MACRO_ONCE, MACRO_HOLD, MACRO_TOGGLE = 1, 2, 4


class KeymapError(ValueError):
    pass


@dataclass(frozen=True)
class NoAction:
    pass


@dataclass(frozen=True)
class Key:
    hid: int
    mods: int = 0
    high: bool = False  # True when the HID code sits in byte 2 (shortcut-preset layout)


@dataclass(frozen=True)
class Mouse:
    code: int           # 1 left, 2 middle, 3 right, 4 back, 5 forward, 8 wheel up, 9 wheel down
    b2: int = 1
    b3: int = 0


@dataclass(frozen=True)
class Consumer:
    usage: int


@dataclass(frozen=True)
class MacroRef:
    index: int
    mode: int = MACRO_ONCE
    count: int = 1


@dataclass(frozen=True)
class System:
    code: int


@dataclass(frozen=True)
class Lighting:
    a: int
    b: int = 0


@dataclass(frozen=True)
class FnKey:
    pass


@dataclass(frozen=True)
class Raw:
    data: bytes


KeyAction = Union[NoAction, Key, Mouse, Consumer, MacroRef, System, Lighting, FnKey, Raw]


def _byte(name: str, v: int) -> int:
    if type(v) is not int or not 0 <= v <= 0xFF:
        raise KeymapError(f"{name} must be an int in 0..255, got {v!r}")
    return v


def decode_entry(e: bytes) -> KeyAction:
    if len(e) != 4:
        raise KeymapError("entry must be 4 bytes")
    t, b1, b2, b3 = e
    if e == b"\0\0\0\0":
        return NoAction()
    if t == 0x00:
        if b2 and not b3:
            return Key(b2, mods=b1, high=True)
        if not b2:
            return Key(b3, mods=b1)
    if t == 0x01 and b1:
        return Mouse(b1, b2, b3)
    if t == 0x02 and b1 == 0 and (b2 or b3):
        return Consumer((b2 << 8) | b3)
    if t == 0x03 and b1 in (MACRO_ONCE, MACRO_HOLD, MACRO_TOGGLE):
        return MacroRef(b3, mode=b1, count=b2)
    if t == 0x07 and b1 == 0 and b2 == 0:
        return System(b3)
    if t == 0x08 and b3 == 0:
        return Lighting(b1, b2)
    if t == 0x0D and e[1:] == b"\0\0\0":
        return FnKey()
    return Raw(bytes(e))


def encode_entry(a: KeyAction) -> bytes:
    if isinstance(a, NoAction):
        return b"\0\0\0\0"
    if isinstance(a, Key):
        h, m = _byte("hid", a.hid), _byte("mods", a.mods)
        if type(a.high) is not bool:
            raise KeymapError(f"high must be a bool, got {a.high!r}")
        return bytes([0, m, h, 0]) if a.high else bytes([0, m, 0, h])
    if isinstance(a, Mouse):
        return bytes([1, _byte("mouse", a.code), _byte("b2", a.b2), _byte("b3", a.b3)])
    if isinstance(a, Consumer):
        if type(a.usage) is not int or not 0 < a.usage <= 0xFFFF:
            raise KeymapError(f"consumer usage out of range: {a.usage!r}")
        return bytes([2, 0, a.usage >> 8, a.usage & 0xFF])
    if isinstance(a, MacroRef):
        if _byte("mode", a.mode) not in (MACRO_ONCE, MACRO_HOLD, MACRO_TOGGLE):
            raise KeymapError(f"bad macro mode {a.mode}")
        return bytes([3, a.mode, _byte("count", a.count), _byte("index", a.index)])
    if isinstance(a, System):
        return bytes([7, 0, 0, _byte("system", a.code)])
    if isinstance(a, Lighting):
        return bytes([8, _byte("a", a.a), _byte("b", a.b), 0])
    if isinstance(a, FnKey):
        return b"\x0d\0\0\0"
    if isinstance(a, Raw):
        if type(a.data) is not bytes or len(a.data) != 4:
            raise KeymapError("raw entry must be 4 bytes")
        return bytes(a.data)
    raise KeymapError(f"unknown action {a!r}")


def decode_layer(raw: bytes) -> list[KeyAction]:
    if len(raw) != LAYER_SIZE:
        raise KeymapError(f"layer must be {LAYER_SIZE} bytes, got {len(raw)}")
    return [decode_entry(raw[i:i + 4]) for i in range(0, LAYER_SIZE, 4)]


def encode_layer(actions: list[KeyAction]) -> bytes:
    if len(actions) != LAYER_SLOTS:
        raise KeymapError(f"layer needs {LAYER_SLOTS} actions, got {len(actions)}")
    return b"".join(encode_entry(a) for a in actions)


def wired_unsafe(a: KeyAction) -> bool:
    """True if this action types a key the wired NKRO report can't send."""
    return isinstance(a, Key) and a.hid > NKRO_MAX_HID


_TYPES = {"none": NoAction, "key": Key, "mouse": Mouse, "consumer": Consumer, "macro": MacroRef,
          "system": System, "lighting": Lighting, "fn": FnKey, "raw": Raw}
_NAMES = {v: k for k, v in _TYPES.items()}


def action_to_dict(a: KeyAction) -> dict:
    name = _NAMES.get(type(a))
    if name is None:
        raise KeymapError(f"unknown action {a!r}")
    d = {"type": name}
    for k, v in a.__dict__.items():
        d[k] = v.hex() if isinstance(v, bytes) else v
    return d


def action_from_dict(d: dict) -> KeyAction:
    try:
        cls = _TYPES.get(d.get("type"))
        if cls is None:
            raise KeymapError(f"unknown action type {d.get('type')!r}")
        kw = {k: v for k, v in d.items() if k != "type"}
        if cls is Raw:
            kw["data"] = bytes.fromhex(kw["data"])
        a = cls(**kw)
    except KeymapError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError) as e:
        raise KeymapError(str(e)) from e
    encode_entry(a)  # reject bad values at load time, not at write time
    return a


# Slot -> label for the Cavalry 87W base layer (slot = column * 6 + row). Read from the real keyboard.
KEY_SLOTS: dict[int, str] = {
    0: "Esc", 1: "`", 2: "Tab", 3: "CapsLock", 4: "LShift", 5: "LCtrl", 7: "1", 8: "Q", 9: "A",
    10: "Z", 11: "LWin", 12: "F1", 13: "2", 14: "W", 15: "S", 16: "X", 17: "LAlt", 18: "F2",
    19: "3", 20: "E", 21: "D", 22: "C", 24: "F3", 25: "4", 26: "R", 27: "F", 28: "V", 30: "F4",
    31: "5", 32: "T", 33: "G", 34: "B", 35: "Space", 36: "F5", 37: "6", 38: "Y", 39: "H",
    40: "N", 42: "F6", 43: "7", 44: "U", 45: "J", 46: "M", 48: "F7", 49: "8", 50: "I", 51: "K",
    52: ",", 53: "RAlt", 54: "F8", 55: "9", 56: "O", 57: "L", 58: ".", 59: "Fn", 60: "F9",
    61: "0", 62: "P", 63: ";", 64: "/", 65: "Menu", 66: "F10", 67: "-", 68: "[", 69: "'",
    70: "Intl\\", 72: "F11", 73: "=", 74: "]", 75: "\\", 76: "ISO\\", 78: "F12",
    79: "Backspace", 80: "\\ (alt)", 81: "Enter", 82: "RShift", 83: "RCtrl", 84: "PrintScreen",
    85: "Insert", 86: "Delete", 89: "Left", 90: "ScrollLock", 91: "Home", 92: "End", 94: "Up",
    95: "Down", 96: "Pause", 97: "PageUp", 98: "PageDown", 101: "Right",
}
SLOT_BY_NAME: dict[str, int] = {v: k for k, v in KEY_SLOTS.items()}

MODIFIERS = {0x01: "LCtrl", 0x02: "LShift", 0x04: "LAlt", 0x08: "LWin",
             0x10: "RCtrl", 0x20: "RShift", 0x40: "RAlt", 0x80: "RWin"}
SYSTEM_NAMES = {0x01: "Lock Win key", 0x04: "Factory reset", 0x05: "Bluetooth 1",
                0x06: "Bluetooth 2", 0x08: "2.4G mode", 0x09: "Wired mode",
                0x0A: "Unknown (factory Fn+G)", 0x0B: "Backlight on/off",
                0x10: "Clear Bluetooth pairing", 0x15: "Windows mode", 0x16: "Mac mode"}
LIGHTING_NAMES = {(0, 0): "Next effect", (1, 0): "Change direction", (2, 0): "Next color",
                  (3, 1): "Brightness up", (3, 2): "Brightness down",
                  (4, 1): "Speed up", (4, 2): "Speed down"}
CONSUMER_NAMES = {0x00E2: "Mute", 0x00E9: "Volume up", 0x00EA: "Volume down",
                  0x00CD: "Play/Pause", 0x00B5: "Next track", 0x00B6: "Previous track",
                  0x00B7: "Stop", 0x006F: "Screen brightness up", 0x0070: "Screen brightness down",
                  0x018A: "Mail", 0x0192: "Calculator", 0x0194: "My Computer",
                  0x0221: "Search", 0x0223: "Browser home", 0x0224: "Browser back",
                  0x0225: "Browser forward", 0x0226: "Browser stop", 0x0227: "Browser refresh",
                  0x022A: "Favorites"}
