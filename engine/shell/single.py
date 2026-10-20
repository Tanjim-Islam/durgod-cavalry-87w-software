"""Only one copy runs; a second launch brings the first one forward."""
from __future__ import annotations

import win32api
import win32con
import win32event
import win32gui
import winerror

_handle = None


def acquire(name: str = "Cavalry87.Single") -> bool:
    global _handle
    _handle = win32event.CreateMutex(None, False, name)
    return win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS


def focus_existing(title: str = "Cavalry 87W") -> None:
    hwnd = win32gui.FindWindow(None, title)
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
