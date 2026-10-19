"""Saved per-key colors (3 planes R,G,B of 126) and effect palettes (23 groups x 7 RGB)."""
from __future__ import annotations

from ..protocol import KEY_COLORS_SIZE, LAYER_SLOTS, PALETTE_GROUPS, PALETTE_SIZE

RGB = tuple[int, int, int]
DEFAULT_PALETTE_GROUP: list[RGB] = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
                                    (255, 0, 255), (0, 255, 255), (255, 255, 255)]


class ColorError(ValueError):
    pass


def _seq(v, n: int, what: str) -> None:
    if not isinstance(v, (list, tuple)) or len(v) != n:
        raise ColorError(f"{what} must be a sequence of {n}")


def _check(c) -> RGB:
    _seq(c, 3, f"color {c!r}")
    if any(type(v) is not int or not 0 <= v <= 255 for v in c):
        raise ColorError(f"bad color {c!r}")
    return (c[0], c[1], c[2])


def _bytes(raw, n: int, what: str) -> None:
    if not isinstance(raw, bytes) or len(raw) != n:
        raise ColorError(f"{what} must be {n} bytes")


def decode_key_colors(raw: bytes) -> list[RGB]:
    _bytes(raw, KEY_COLORS_SIZE, "key colors")
    n = LAYER_SLOTS
    return [(raw[i], raw[n + i], raw[2 * n + i]) for i in range(n)]


def encode_key_colors(colors: list[RGB]) -> bytes:
    _seq(colors, LAYER_SLOTS, "key colors")
    cs = [_check(c) for c in colors]
    return bytes(c[0] for c in cs) + bytes(c[1] for c in cs) + bytes(c[2] for c in cs)


def decode_palette(raw: bytes) -> list[list[RGB]]:
    _bytes(raw, PALETTE_SIZE, "palette")
    return [[tuple(raw[g * 21 + i * 3:g * 21 + i * 3 + 3]) for i in range(7)]
            for g in range(PALETTE_GROUPS)]


def encode_palette(groups: list[list[RGB]]) -> bytes:
    _seq(groups, PALETTE_GROUPS, "palette")
    for g in groups:
        _seq(g, 7, "palette group")
    out = b"".join(bytes(_check(c)) for g in groups for c in g)
    assert len(out) == PALETTE_SIZE
    return out
