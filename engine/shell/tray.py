"""Tray icon on its own thread: left click -> main window, right click -> flyout. No native menu."""
from __future__ import annotations

import ctypes
import logging
import threading

import win32api
import win32con
import win32gui

from .single import QUIT_MESSAGE, SHOW_MAIN_MESSAGE, TRAY_WINDOW

log = logging.getLogger("cavalry")

WM_TRAY = win32con.WM_USER + 20
RETRY_TIMER, RETRY_MS, RETRY_MAX = 1, 2000, 15

WM_LBUTTONUP, WM_RBUTTONUP = win32con.WM_LBUTTONUP, win32con.WM_RBUTTONUP
WM_CONTEXTMENU, WM_MOUSEMOVE = win32con.WM_CONTEXTMENU, win32con.WM_MOUSEMOVE

_user32 = ctypes.windll.user32
_user32.SetTimer.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_void_p]
_user32.KillTimer.argtypes = [ctypes.c_void_p, ctypes.c_size_t]


def click_action(lparam: int) -> str | None:
    msg = lparam & 0xFFFF
    if msg == WM_LBUTTONUP:
        return "main"
    if msg in (WM_RBUTTONUP, WM_CONTEXTMENU):
        return "flyout"
    return None


def session_action(msg: int, wparam: int) -> str | None:
    if msg == win32con.WM_QUERYENDSESSION:
        return "ending"
    if msg == win32con.WM_ENDSESSION:
        return "end" if wparam else "cancelled"
    return None


class Tray:
    def __init__(self, icon_path: str, tooltip: str, on_main, on_flyout, on_session=lambda action: None,
                 on_quit=lambda: None):
        self.icon_path, self.tooltip = icon_path, tooltip
        self.on_main, self.on_flyout, self.on_session, self.on_quit = on_main, on_flyout, on_session, on_quit
        self._hwnd = None
        self._added = False
        self._attempts = 0
        self._taskbar_created = 0
        self._show_main = 0
        self._quit = 0
        self._thread = threading.Thread(target=self._run, name="cavalry-tray", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        if self._hwnd:
            try:
                win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                log.exception("could not close the tray window")
        if self._thread.is_alive():
            self._thread.join(timeout=2)

    def _call(self, fn, *args) -> None:
        try:
            fn(*args)
        except Exception:
            log.exception("tray callback failed")

    def _proc(self, hwnd, msg, wparam, lparam):
        session = session_action(msg, wparam)
        if session:  # sign-out/shutdown: never veto it, let the app close for real
            self._call(self.on_session, session)
            return 1 if msg == win32con.WM_QUERYENDSESSION else 0
        if msg == WM_TRAY:
            action = click_action(lparam)
            if action == "main":
                self._call(self.on_main)
            elif action == "flyout":
                self._call(self.on_flyout, win32api.GetCursorPos())
            return 0
        if msg == self._show_main and msg:   # a second launch asked us to come forward
            self._call(self.on_main)
            return 0
        if msg == self._quit and msg:        # the installer is about to replace or remove us
            self._call(self.on_quit)
            return 0
        if msg == self._taskbar_created:
            self._added = False
            self._attempts = 0
            self._try_add()
            return 0
        if msg == win32con.WM_TIMER and wparam == RETRY_TIMER:
            self._try_add()
            return 0
        if msg == win32con.WM_CLOSE:
            if self._added:
                try:
                    win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (hwnd, 1))
                except Exception:
                    log.exception("could not remove the tray icon")
            win32gui.DestroyWindow(hwnd)
            return 0
        if msg == win32con.WM_DESTROY:
            self._hwnd = None
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _add_icon(self) -> None:
        size = win32api.GetSystemMetrics(win32con.SM_CXSMICON)
        icon = win32gui.LoadImage(0, self.icon_path, win32con.IMAGE_ICON, size, size, win32con.LR_LOADFROMFILE)
        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, (self._hwnd, 1, flags, WM_TRAY, icon, self.tooltip))

    def _try_add(self) -> None:
        """Explorer may not be ready at logon: retry on a timer until the icon is in."""
        try:
            self._add_icon()
        except Exception:
            log.exception("could not add the tray icon (attempt %d)", self._attempts + 1)
            self._attempts += 1
            if self._attempts < RETRY_MAX:
                _user32.SetTimer(self._hwnd, RETRY_TIMER, RETRY_MS, None)
                return
        else:
            self._added = True
        _user32.KillTimer(self._hwnd, RETRY_TIMER)

    def _run(self) -> None:
        try:
            self._taskbar_created = win32gui.RegisterWindowMessage("TaskbarCreated")
            self._show_main = win32gui.RegisterWindowMessage(SHOW_MAIN_MESSAGE)
            self._quit = win32gui.RegisterWindowMessage(QUIT_MESSAGE)
            wc = win32gui.WNDCLASS()
            wc.lpszClassName = f"Cavalry87Tray{id(self)}"
            wc.lpfnWndProc = self._proc
            wc.hInstance = win32api.GetModuleHandle(None)
            win32gui.RegisterClass(wc)
            self._hwnd = win32gui.CreateWindow(wc.lpszClassName, TRAY_WINDOW, 0, 0, 0, 0, 0, 0, 0,
                                               wc.hInstance, None)
            self._try_add()
            win32gui.PumpMessages()
        except Exception:
            log.exception("tray thread failed")
