"""Custom title bar support: hide the native caption but keep a real window (resize, snap, shadow, animations).

The page draws its own bar; CSS `app-region: drag` makes WebView2 report it to Windows as the caption.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import time

log = logging.getLogger("cavalry")

WM_NCCALCSIZE = 0x0083
WM_SIZE = 0x0005
WM_WINDOWPOSCHANGING = 0x0046
WM_ENTERSIZEMOVE, WM_EXITSIZEMOVE = 0x0231, 0x0232
SIZE_RESTORED, SIZE_MINIMIZED, SIZE_MAXIMIZED = 0, 1, 2
SWP_NOSIZE = 0x0001
RESTORE_GUARD_S = 0.5
GWLP_WNDPROC = -4
SWP_FRAMECHANGED = 0x0020
SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0010 | SWP_FRAMECHANGED   # no size/move/zorder/activate
DWMWA_USE_IMMERSIVE_DARK_MODE = 20

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

_u32 = ctypes.WinDLL("user32", use_last_error=True)
_u32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_void_p]
_u32.SetWindowLongPtrW.restype = ctypes.c_void_p
_u32.CallWindowProcW.argtypes = [ctypes.c_void_p, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
_u32.CallWindowProcW.restype = LRESULT
_u32.IsZoomed.argtypes = [wt.HWND]
_u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
_u32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]


def client_top(old_top: int, old_left: int, new_left: int, zoomed: bool) -> int:
    """Top of the client area once the caption is gone. A maximized window hangs its frame off-screen,
    so its client starts one frame width lower (the frame is as thick on top as on the sides)."""
    return old_top + (new_left - old_left if zoomed else 0)


class WINDOWPOS(ctypes.Structure):
    _fields_ = [("hwnd", wt.HWND), ("after", wt.HWND), ("x", ctypes.c_int), ("y", ctypes.c_int),
                ("cx", ctypes.c_int), ("cy", ctypes.c_int), ("flags", wt.UINT)]


class CaptionRemover:
    def __init__(self, hwnd: int, clock=time.monotonic):
        self.hwnd, self._clock = hwnd, clock
        self._unrestored = False   # maximized or minimized: the next restore gets the guard
        self._restored_size: tuple[int, int, float] | None = None   # (cx, cy, when) right after a restore
        self._proc = WNDPROC(self._wndproc)   # kept on self so it is never garbage collected
        self._old = None

    def install(self) -> None:
        old = _u32.SetWindowLongPtrW(self.hwnd, GWLP_WNDPROC, ctypes.cast(self._proc, ctypes.c_void_p))
        if not old:
            raise OSError(f"SetWindowLongPtrW failed: {ctypes.get_last_error()}")
        self._old = old
        _dark_frame(self.hwnd)
        _u32.SetWindowPos(self.hwnd, None, 0, 0, 0, 0, SWP_FLAGS)

    def uninstall(self) -> None:
        if self._old:
            _u32.SetWindowLongPtrW(self.hwnd, GWLP_WNDPROC, self._old)
            self._old = None

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_NCCALCSIZE and wparam:
                rect = wt.RECT.from_address(lparam)
                top, left = rect.top, rect.left
                res = _u32.CallWindowProcW(self._old, hwnd, msg, wparam, lparam)
                rect.top = client_top(top, left, rect.left, bool(_u32.IsZoomed(hwnd)))
                return res
            if msg == WM_SIZE:
                self._track_restore(hwnd, wparam)
            elif msg == WM_WINDOWPOSCHANGING:
                self._keep_restored_size(lparam)
            elif msg in (WM_ENTERSIZEMOVE, WM_EXITSIZEMOVE):
                self._restored_size = None   # the user is sizing: never override them
        except Exception:
            log.exception("custom title bar: window message %#x failed", msg)
        return _u32.CallWindowProcW(self._old, hwnd, msg, wparam, lparam)

    def _track_restore(self, hwnd, kind) -> None:
        if kind in (SIZE_MINIMIZED, SIZE_MAXIMIZED):
            self._unrestored = True
        elif kind == SIZE_RESTORED and self._unrestored:
            self._unrestored = False
            r = wt.RECT()
            _u32.GetWindowRect(hwnd, ctypes.byref(r))
            self._restored_size = (r.right - r.left, r.bottom - r.top, self._clock())

    def _keep_restored_size(self, lparam) -> None:
        """WinForms follows a restore (from maximized or minimized) with a resize that adds the hidden caption's height back; undo it."""
        wp = WINDOWPOS.from_address(lparam)
        self._restored_size = keep_size(wp, self._restored_size, self._clock())


def keep_size(wp, restored, now):
    """Pins the first resize after a restore to the size Windows restored; returns the guard left over."""
    if not restored or wp.flags & SWP_NOSIZE:
        return restored
    cx, cy, when = restored
    if now - when <= RESTORE_GUARD_S:
        wp.cx, wp.cy = cx, cy
    return None


def _dark_frame(hwnd: int) -> None:
    """Dark system bits (resize ghost, 1px border) so nothing white flashes around the app."""
    try:
        on = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(on),
                                                  ctypes.sizeof(on))
    except Exception:
        log.warning("could not set the dark window frame")


def enable_app_regions() -> None:
    """Turn on WebView2's non-client regions before the first navigation so `app-region: drag` works."""
    from webview.platforms import edgechromium

    original = edgechromium.EdgeChrome.on_webview_ready
    if getattr(original, "_cavalry", False):
        return

    def on_webview_ready(self, sender, args):
        try:
            if args.IsSuccess:
                sender.CoreWebView2.Settings.IsNonClientRegionSupportEnabled = True
        except Exception:
            log.warning("WebView2 non-client regions unavailable; the title bar can't be dragged")
        return original(self, sender, args)

    on_webview_ready._cavalry = True
    edgechromium.EdgeChrome.on_webview_ready = on_webview_ready
