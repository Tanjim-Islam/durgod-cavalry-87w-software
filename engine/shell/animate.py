"""Fade and slide for the tray flyout: a layered window's alpha plus its position, stepped about 60 times a second.

WebView2 content follows the window's alpha, so the whole flyout fades, not just its frame.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading
import time

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x2
SWP_MOVE_ONLY = 0x0001 | 0x0004 | 0x0010   # no size, no z-order, no activate
DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND = 33, 2
FRAME_S = 1 / 60

_u32 = ctypes.WinDLL("user32", use_last_error=True)
_u32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
_u32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
_u32.SetLayeredWindowAttributes.argtypes = [wt.HWND, wt.COLORREF, wt.BYTE, wt.DWORD]
_u32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]


def ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def frames(start, end, a0: int, a1: int, duration: float):
    """(x, y, alpha) for each frame of the move, ending exactly on the target."""
    n = max(1, round(duration / FRAME_S))
    for i in range(1, n + 1):
        e = ease_out(i / n)
        yield (round(start[0] + (end[0] - start[0]) * e), round(start[1] + (end[1] - start[1]) * e),
               round(a0 + (a1 - a0) * e))


class Fader:
    """One window's open/close animation. A newer animation cancels a running one."""

    def __init__(self, hwnd: int, sleep=time.sleep):
        self.hwnd, self._sleep = hwnd, sleep
        self._gen = 0
        self._lock = threading.Lock()
        _u32.SetWindowLongW(hwnd, GWL_EXSTYLE, _u32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_LAYERED)
        self.alpha(255)
        corner = ctypes.c_int(DWMWCP_ROUND)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(corner),
                                                  ctypes.sizeof(corner))

    def alpha(self, a: int) -> None:
        _u32.SetLayeredWindowAttributes(self.hwnd, 0, max(0, min(255, a)), LWA_ALPHA)

    def jump(self, xy: tuple[int, int], a: int) -> None:
        with self._lock:
            self._gen += 1
        _u32.SetWindowPos(self.hwnd, None, xy[0], xy[1], 0, 0, SWP_MOVE_ONLY)
        self.alpha(a)

    def run(self, start, end, a0: int, a1: int, duration: float) -> bool:
        """Animate; False if a newer animation took over before this one finished."""
        with self._lock:
            self._gen += 1
            gen = self._gen
        for x, y, a in frames(start, end, a0, a1, duration):
            if self._gen != gen:
                return False
            _u32.SetWindowPos(self.hwnd, None, x, y, 0, 0, SWP_MOVE_ONLY)
            self.alpha(a)
            self._sleep(FRAME_S)
        return self._gen == gen
