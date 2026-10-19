"""Macro buffer: N x [offset u16][size u16] table + blobs, always 4096 bytes (cmd 0x05 / radio 0x03)."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..protocol import MACRO_SIZE

KINDS = {"key": 0, "modifier": 1, "mouse_button": 2, "mouse_x": 3, "mouse_y": 4, "wheel": 5}
KIND_NAMES = {v: k for k, v in KINDS.items()}
MAX_DELAY = 0xFFFFF
MAX_NAME = 30


class MacroError(ValueError):
    pass


@dataclass(frozen=True)
class MacroEvent:
    kind: str
    code: int
    release: bool = False
    delay_ms: int = 0

    def __post_init__(self):
        if self.kind not in KINDS:
            raise MacroError(f"unknown event kind {self.kind!r}")
        if not 0 <= self.code <= 0xFF:
            raise MacroError(f"code out of range: {self.code}")
        if not 0 <= self.delay_ms <= MAX_DELAY:
            raise MacroError(f"delay must be 0..{MAX_DELAY} ms")


@dataclass
class Macro:
    name: str
    events: list[MacroEvent] = field(default_factory=list)


def tap(hid: int, delay_ms: int = 16) -> list[MacroEvent]:
    return [MacroEvent("key", hid, False, delay_ms), MacroEvent("key", hid, True, delay_ms)]


def encode_macro(m: Macro) -> bytes:
    if len(m.name) > MAX_NAME:
        raise MacroError(f"name longer than {MAX_NAME} characters")
    name = m.name.encode("utf-16-le")
    out = bytearray([len(name)]) + name
    for e in m.events:
        d = e.delay_ms
        out += bytes([(KINDS[e.kind] << 4) | (d >> 16 & 0x0F) | (0x80 if e.release else 0),
                      d >> 8 & 0xFF, d & 0xFF, e.code])
    return bytes(out)


def decode_macro(blob: bytes) -> Macro:
    n = blob[0]
    name = blob[1:1 + n].decode("utf-16-le")
    events = []
    for i in range(1 + n, len(blob) - 3, 4):
        b0, b1, b2, code = blob[i:i + 4]
        kind = (b0 >> 4) & 0x07
        if kind not in KIND_NAMES:
            raise MacroError(f"bad event type {kind}")
        events.append(MacroEvent(KIND_NAMES[kind], code, bool(b0 & 0x80),
                                 ((b0 & 0x0F) << 16) | (b1 << 8) | b2))
    return Macro(name, events)


def encode_macros(macros: list[Macro]) -> bytes:
    blobs = [encode_macro(m) for m in macros]
    table, data, off = bytearray(), bytearray(), 4 * len(blobs)
    for b in blobs:
        table += bytes([off & 0xFF, off >> 8, len(b) & 0xFF, len(b) >> 8])
        data += b
        off += len(b)
    buf = bytes(table + data)
    if len(buf) > MACRO_SIZE:
        raise MacroError(f"macros need {len(buf)} bytes, limit is {MACRO_SIZE}")
    return buf + bytes(MACRO_SIZE - len(buf))


def decode_macros(raw: bytes) -> list[Macro]:
    if len(raw) != MACRO_SIZE:
        raise MacroError(f"macro buffer must be {MACRO_SIZE} bytes")
    first = raw[0] | raw[1] << 8
    if first == 0:
        return []
    if first % 4 or first > MACRO_SIZE:
        raise MacroError("corrupt macro table")
    out = []
    for i in range(first // 4):
        off = raw[i * 4] | raw[i * 4 + 1] << 8
        size = raw[i * 4 + 2] | raw[i * 4 + 3] << 8
        if off + size > MACRO_SIZE:
            raise MacroError("macro entry outside buffer")
        out.append(decode_macro(raw[off:off + size]))
    return out


def macro_to_dict(m: Macro) -> dict:
    return {"name": m.name, "events": [e.__dict__.copy() for e in m.events]}


def macro_from_dict(d: dict) -> Macro:
    return Macro(d["name"], [MacroEvent(**e) for e in d["events"]])
