"""Factory Fn shortcuts (manual + hidden Fn+O/Fn+P) and live comparison with the Fn layer."""
from __future__ import annotations

from dataclasses import dataclass

from .keymap import (CONSUMER_NAMES, LIGHTING_NAMES, MODIFIERS, SYSTEM_NAMES, Consumer, FnKey,
                     Key, KeyAction, Lighting, MacroRef, Mouse, NoAction, Raw, System,
                     action_to_dict)


@dataclass(frozen=True)
class Shortcut:
    keys: str
    slot: int
    group: str
    label: str
    original: KeyAction


SHORTCUTS: list[Shortcut] = [
    Shortcut("Fn + F1", 12, "Media", "Mute", Consumer(0x00E2)),
    Shortcut("Fn + F2", 18, "Media", "Volume down", Consumer(0x00EA)),
    Shortcut("Fn + F3", 24, "Media", "Volume up", Consumer(0x00E9)),
    Shortcut("Fn + F10", 66, "Media", "Browser home", Consumer(0x0223)),
    Shortcut("Fn + F11", 72, "Media", "My Computer", Consumer(0x0194)),
    Shortcut("Fn + F4", 30, "Lighting", "Backlight on/off", System(0x0B)),
    Shortcut("Fn + F5", 36, "Lighting", "Brightness up", Lighting(3, 1)),
    Shortcut("Fn + F6", 42, "Lighting", "Brightness down", Lighting(3, 2)),
    Shortcut("Fn + F7", 48, "Lighting", "Effect slower", Lighting(4, 2)),
    Shortcut("Fn + F8", 54, "Lighting", "Effect faster", Lighting(4, 1)),
    Shortcut("Fn + F12", 78, "Lighting", "Next effect", Lighting(0, 0)),
    Shortcut("Fn + 9", 55, "Lighting", "Change direction", Lighting(1, 0)),
    Shortcut("Fn + 0", 61, "Lighting", "Next color", Lighting(2, 0)),
    Shortcut("Fn + PrtSc", 84, "Connection", "Wired mode", System(0x09)),
    Shortcut("Fn + ScrLk", 90, "Connection", "2.4G mode (hold 3 s: re-pair dongle)", System(0x08)),
    Shortcut("Fn + Pause", 96, "Connection", "Bluetooth 1 (hold: pairing)", System(0x05)),
    Shortcut("Fn + PgUp", 97, "Connection", "Bluetooth 2 (hold: pairing)", System(0x06)),
    Shortcut("Fn + Ins", 85, "Connection", "Clear Bluetooth pairing", System(0x10)),
    Shortcut("Fn + F9", 60, "System", "Lock Win key", System(0x01)),
    Shortcut("Fn + Win", 11, "System", "Lock Win key", System(0x01)),
    Shortcut("Fn + O", 56, "System", "Windows mode (not in manual)", System(0x15)),
    Shortcut("Fn + P", 62, "System", "Mac mode (not in manual)", System(0x16)),
    Shortcut("Fn + Del", 86, "System", "Factory reset", System(0x04)),
    Shortcut("Fn + G", 33, "System", "Unknown factory function", System(0x0A)),
]
MANUAL_ONLY = [("Fn + Pause + PgUp", "Connection", "Bluetooth broadcast (discoverable) mode")]


def describe(a: KeyAction) -> str:
    if isinstance(a, NoAction):
        return "Nothing"
    if isinstance(a, Key):
        mods = [n for bit, n in MODIFIERS.items() if a.mods & bit]
        return " + ".join(mods + ([f"HID {a.hid:#04x}"] if a.hid else []))
    if isinstance(a, Consumer):
        return CONSUMER_NAMES.get(a.usage, f"Media {a.usage:#06x}")
    if isinstance(a, System):
        return SYSTEM_NAMES.get(a.code, f"System {a.code:#04x}")
    if isinstance(a, Lighting):
        return LIGHTING_NAMES.get((a.a, a.b), f"Lighting {a.a}/{a.b}")
    if isinstance(a, MacroRef):
        return f"Macro {a.index + 1}"
    if isinstance(a, Mouse):
        return {1: "Left click", 2: "Middle click", 3: "Right click", 4: "Back", 5: "Forward",
                8: "Wheel up", 9: "Wheel down"}.get(a.code, f"Mouse {a.code}")
    if isinstance(a, FnKey):
        return "Fn"
    return f"Raw {a.data.hex()}" if isinstance(a, Raw) else repr(a)


def shortcut_table(fn_layer: list[KeyAction]) -> list[dict]:
    rows = []
    for s in SHORTCUTS:
        cur = fn_layer[s.slot]
        rows.append({"keys": s.keys, "group": s.group, "label": s.label, "slot": s.slot,
                     "current": describe(cur), "current_action": action_to_dict(cur),
                     "changed": cur != s.original})
    for keys, group, label in MANUAL_ONLY:
        rows.append({"keys": keys, "group": group, "label": label, "slot": None,
                     "current": label, "current_action": None, "changed": False})
    return rows
