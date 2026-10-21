"""Where the flyout goes: next to the tray icon, on the side away from the taskbar, inside the work area."""
from __future__ import annotations

MARGIN = 10
SLIDE = 14   # how far (logical px) the flyout travels as it opens


def edge(anchor: tuple[int, int, int, int], work: tuple[int, int, int, int]) -> str:
    """Which side the icon sits on: the taskbar's edge, or "inside" (e.g. the hidden icons popup)."""
    l, t, r, b = anchor
    wl, wt, wr, wb = work
    cx, cy = (l + r) // 2, (t + b) // 2
    if cy >= wb:
        return "bottom"
    if cy <= wt:
        return "top"
    if cx >= wr:
        return "right"
    if cx <= wl:
        return "left"
    return "inside"


def place(anchor: tuple[int, int, int, int], work: tuple[int, int, int, int],
          size: tuple[int, int], slide: int = SLIDE) -> tuple[int, int, int, int]:
    """Top-left (x, y) right next to the icon, plus (dx, dy): where the open animation starts from,
    relative to that, so it grows out of the icon's side."""
    l, t, r, b = anchor
    wl, wt, wr, wb = work
    w, h = size
    x, y = (l + r) // 2 - w // 2, (t + b) // 2 - h // 2
    side = edge(anchor, work)
    if side == "bottom":
        y, d = wb - MARGIN - h, (0, slide)
    elif side == "top":
        y, d = wt + MARGIN, (0, -slide)
    elif side == "right":
        x, d = wr - MARGIN - w, (slide, 0)
    elif side == "left":
        x, d = wl + MARGIN, (-slide, 0)
    elif t - MARGIN - h >= wt + MARGIN:
        y, d = t - MARGIN - h, (0, slide)        # above the icon in the popup
    else:
        y, d = b + MARGIN, (0, -slide)           # no room above: below it
    x = min(max(x, wl + MARGIN), wr - MARGIN - w)
    y = min(max(y, wt + MARGIN), wb - MARGIN - h)
    return x, y, *d
