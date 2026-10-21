"""Checks before any window exists, and a native dialog for failures the web UI can't show."""
from __future__ import annotations

import logging
import os
import winreg

import win32api
import win32con

log = logging.getLogger("cavalry")

WEBVIEW2_DOWNLOAD = "https://developer.microsoft.com/microsoft-edge/webview2/"
_WEBVIEW2_KEY = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def webview2_version() -> str | None:
    """Installed Edge WebView2 Runtime version, or None. Without it pywebview silently falls back to IE."""
    for hive, path in ((winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\{_WEBVIEW2_KEY}"),
                       (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\{_WEBVIEW2_KEY}"),
                       (winreg.HKEY_CURRENT_USER, rf"SOFTWARE\{_WEBVIEW2_KEY}")):
        try:
            with winreg.OpenKey(hive, path) as k:
                version = str(winreg.QueryValueEx(k, "pv")[0])
        except OSError:
            continue
        if version and version != "0.0.0.0":
            return version
    return None


def fatal(title: str, message: str, url: str | None = None) -> None:
    """Native error dialog; with a url, Yes opens it in the browser."""
    style = win32con.MB_ICONERROR | win32con.MB_SETFOREGROUND
    style |= win32con.MB_YESNO if url else win32con.MB_OK
    try:
        if win32api.MessageBox(0, message, title, style) == win32con.IDYES and url:
            os.startfile(url)
    except Exception:
        log.exception("could not show the error dialog")
