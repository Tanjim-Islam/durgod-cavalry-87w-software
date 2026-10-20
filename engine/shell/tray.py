"""Tray icon on its own thread: left click -> main window, right click -> flyout. No native menu."""
from __future__ import annotations

import threading

import win32api
import win32con
import win32gui

WM_TRAY = win32con.WM_USER + 20
WM_LBUTTONUP, WM_RBUTTONUP = win32con.WM_LBUTTONUP, win32con.WM_RBUTTONUP
WM_CONTEXTMENU, WM_MOUSEMOVE = win32con.WM_CONTEXTMENU, win32con.WM_MOUSEMOVE


def click_action(lparam: int) -> str | None:
    msg = lparam & 0xFFFF
    if msg == WM_LBUTTONUP:
        return "main"
    if msg in (WM_RBUTTONUP, WM_CONTEXTMENU):
        return "flyout"
    return None


class Tray:
    def __init__(self, icon_path: str, tooltip: str, on_main, on_flyout):
        self.icon_path, self.tooltip = icon_path, tooltip
        self.on_main, self.on_flyout = on_main, on_flyout
        self._hwnd = None
        self._thread = threading.Thread(target=self._run, name="cavalry-tray", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        if self._hwnd:
            win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)

    def _proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY:
            action = click_action(lparam)
            if action == "main":
                self.on_main()
            elif action == "flyout":
                self.on_flyout(win32api.GetCursorPos())
            return 0
        if msg == self._taskbar_created:
            self._add_icon()
            return 0
        if msg == win32con.WM_CLOSE:
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (hwnd, 1))
            win32gui.DestroyWindow(hwnd)
            return 0
        if msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _add_icon(self) -> None:
        icon = win32gui.LoadImage(0, self.icon_path, win32con.IMAGE_ICON, 0, 0,
                                  win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE)
        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, (self._hwnd, 1, flags, WM_TRAY, icon, self.tooltip))

    def _run(self) -> None:
        self._taskbar_created = win32gui.RegisterWindowMessage("TaskbarCreated")
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = "Cavalry87Tray"
        wc.lpfnWndProc = self._proc
        wc.hInstance = win32api.GetModuleHandle(None)
        win32gui.RegisterClass(wc)
        self._hwnd = win32gui.CreateWindow(wc.lpszClassName, "Cavalry87Tray", 0, 0, 0, 0, 0, 0, 0,
                                           wc.hInstance, None)
        self._add_icon()
        win32gui.PumpMessages()
