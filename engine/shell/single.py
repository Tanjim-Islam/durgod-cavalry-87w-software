"""Only one copy runs; a second launch brings the first one forward."""
from __future__ import annotations

import ctypes
import logging

import win32api
import win32event
import win32gui
import win32process
import winerror

log = logging.getLogger("cavalry")
SHOW_MAIN_MESSAGE = "Cavalry87.ShowMain"
QUIT_MESSAGE = "Cavalry87.Quit"   # sent by the installer and uninstaller
TRAY_WINDOW = "Cavalry87Tray"

_handle = None


def acquire(name: str = "Cavalry87.Single") -> bool:
    global _handle
    _handle = win32event.CreateMutex(None, False, name)
    return win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS


def focus_existing() -> bool:
    """Ask the running copy to open its window. It does the showing itself, so a copy that lives only in
    the tray comes forward properly; we just lend it our right to take the foreground."""
    try:
        tray = win32gui.FindWindow(None, TRAY_WINDOW)
        if not tray:
            return False
        ctypes.windll.user32.AllowSetForegroundWindow(win32process.GetWindowThreadProcessId(tray)[1])
        win32gui.PostMessage(tray, win32gui.RegisterWindowMessage(SHOW_MAIN_MESSAGE), 0, 0)
        return True
    except Exception:
        log.exception("could not reach the running copy")
        return False
