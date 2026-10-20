"""Start with Windows: a per-user Run key value."""
from __future__ import annotations

import winreg as _winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "Cavalry87"


class Autostart:
    def __init__(self, command: str, reg=_winreg):
        self.command, self.reg = command, reg

    def enabled(self) -> bool:
        try:
            with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER, RUN_KEY, 0, self.reg.KEY_READ) as k:
                return self.reg.QueryValueEx(k, VALUE)[0] == self.command
        except FileNotFoundError:
            return False

    def set(self, on: bool) -> None:
        with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER, RUN_KEY, 0, self.reg.KEY_SET_VALUE) as k:
            if on:
                self.reg.SetValueEx(k, VALUE, 0, self.reg.REG_SZ, self.command)
            else:
                try:
                    self.reg.DeleteValue(k, VALUE)
                except FileNotFoundError:
                    pass
