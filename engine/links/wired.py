"""Cable link: HID feature report 6 (520 bytes) on interface 1."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from typing import Protocol

import hid

from ..protocol import (CONFIG_SIGNATURE, CONFIG_SIZE, KEY_COLORS_SIZE, LAYER_SIZE, MACRO_BLOCK,
                        MACRO_SIZE, PALETTE_SIZE, WIRED_PID, WIRED_VID, Wired)
from .base import Link, LinkError, SizeGuardError, guard


class FeatureDevice(Protocol):
    def set_feature(self, data: bytes) -> None: ...
    def get_feature(self, report_id: int, size: int) -> bytes: ...
    def close(self) -> None: ...


def find_wired_path() -> str | None:
    try:
        devices = hid.enumerate(WIRED_VID, WIRED_PID)
    except OSError:
        return None
    for d in devices:
        if d["usage_page"] == 0xFF00 and b"col06" in d["path"].lower():
            return d["path"].decode()
    return None


class WinFeatureDevice:
    """Raw HidD_SetFeature/HidD_GetFeature (hidapi truncates 520-byte feature reads)."""

    def __init__(self, path: str):
        self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._hid = ctypes.WinDLL("hid")
        self._k32.CreateFileW.restype = wt.HANDLE
        self._k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                                          wt.DWORD, wt.DWORD, wt.HANDLE]
        self._hid.HidD_SetFeature.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
        self._hid.HidD_GetFeature.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
        self._h = self._k32.CreateFileW(path, 0xC0000000, 3, None, 3, 0, None)
        if self._h in (None, wt.HANDLE(-1).value):
            raise LinkError(f"cannot open keyboard (error {ctypes.get_last_error()})")

    def set_feature(self, data: bytes) -> None:
        buf = (ctypes.c_ubyte * len(data))(*data)
        if not self._hid.HidD_SetFeature(self._h, buf, len(data)):
            raise LinkError(f"SetFeature failed ({ctypes.get_last_error()})")

    def get_feature(self, report_id: int, size: int) -> bytes:
        buf = (ctypes.c_ubyte * size)()
        buf[0] = report_id
        if not self._hid.HidD_GetFeature(self._h, buf, size):
            raise LinkError(f"GetFeature failed ({ctypes.get_last_error()})")
        return bytes(buf)

    def close(self) -> None:
        self._k32.CloseHandle(self._h)


class WiredLink(Link):
    kind = "wired"

    def __init__(self, dev: FeatureDevice):
        self.dev = dev

    def _xfer(self, cmd: int, sub: int = 0, data: bytes = b"", size: int | None = None,
              count: int = 1, index: int = 0) -> bytes:
        if cmd not in Wired.ALLOWED:
            raise LinkError(f"command {cmd:#x} is not whitelisted")
        size = len(data) if size is None else size
        hdr = bytes([Wired.REPORT_ID, cmd, sub, 0, count, index, size & 0xFF, size >> 8])
        self.dev.set_feature((hdr + data).ljust(Wired.REPORT_SIZE, b"\0"))
        reply = self.dev.get_feature(Wired.REPORT_ID, Wired.REPORT_SIZE)
        # reads echo the request header; anything else is a stale or foreign reply
        if cmd & 0x80 and (len(reply) < 8 or (reply[1], reply[2], reply[5]) != (cmd, sub, index)):
            raise LinkError(f"reply does not match request {cmd:#x}/{sub}/{index}")
        return reply

    def identify(self) -> bytes:
        return self._xfer(Wired.IDENTIFY, 1, size=6)[8:14]

    def read_config(self) -> bytes:
        return self._xfer(Wired.READ_CONFIG, size=CONFIG_SIZE)[8:8 + CONFIG_SIZE]

    def write_config(self, raw: bytes) -> None:
        guard("config", raw, CONFIG_SIZE)
        if raw[0x7E:0x80] != CONFIG_SIGNATURE:
            raise SizeGuardError("refusing to send config without 5a a5 signature")
        self._xfer(Wired.WRITE_CONFIG, data=raw)

    def read_layer(self, n: int) -> bytes:
        return self._xfer(Wired.READ_LAYER, n, size=LAYER_SIZE)[8:8 + LAYER_SIZE]

    def write_layer(self, n: int, raw: bytes) -> None:
        if n not in range(4):
            raise SizeGuardError(f"bad layer {n}")
        self._xfer(Wired.WRITE_LAYER, n, data=guard("layer", raw, LAYER_SIZE))

    def read_macros(self) -> bytes:
        return b"".join(self._xfer(Wired.READ_MACROS, size=MACRO_BLOCK, count=8, index=i)[8:520]
                        for i in range(8))

    def write_macros(self, raw: bytes) -> None:
        guard("macros", raw, MACRO_SIZE)
        for i in range(8):
            self._xfer(Wired.WRITE_MACROS, data=raw[i * MACRO_BLOCK:(i + 1) * MACRO_BLOCK],
                       count=8, index=i)

    def read_key_colors(self) -> bytes:
        return self._xfer(Wired.READ_KEY_COLORS, size=KEY_COLORS_SIZE)[8:8 + KEY_COLORS_SIZE]

    def write_key_colors(self, raw: bytes) -> None:
        self._xfer(Wired.WRITE_KEY_COLORS, data=guard("key_colors", raw, KEY_COLORS_SIZE))

    def read_palette(self) -> bytes:
        return self._xfer(Wired.READ_PALETTE, size=0x200)[8:8 + PALETTE_SIZE]

    def write_palette(self, raw: bytes) -> None:
        self._xfer(Wired.WRITE_PALETTE, data=guard("palette", raw, PALETTE_SIZE))

    def close(self) -> None:
        self.dev.close()
