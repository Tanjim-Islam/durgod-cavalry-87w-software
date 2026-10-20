"""Where the flyout goes: above (or below) the taskbar, near the cursor, inside the work area."""
from __future__ import annotations

MARGIN = 12


def place(cursor: tuple[int, int], work: tuple[int, int, int, int], size: tuple[int, int]) -> tuple[int, int]:
    cx, cy = cursor
    left, top, right, bottom = work
    w, h = size
    x = min(max(cx - w // 2, left + MARGIN), right - MARGIN - w)
    y = bottom - MARGIN - h if cy >= bottom else top + MARGIN if cy <= top else min(cy, bottom - MARGIN - h)
    return x, y
