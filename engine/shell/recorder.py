"""Macro recorder: a low-level keyboard hook feeds a pure recorder that builds macro events."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import threading
import time

from ..codec.macro import MAX_DELAY
from .vkmap import VK_TO_HID, is_modifier

log = logging.getLogger("cavalry")


class Recorder:
    def __init__(self, clock=time.monotonic, max_events: int = 900, allow_injected: bool = False):
        self._clock, self.max_events, self.allow_injected = clock, max_events, allow_injected
        self._lock = threading.Lock()
        self.recording = False
        self.truncated = False
        self._events: list = []
        self._down: set = set()
        self._last = None

    def start(self) -> None:
        with self._lock:
            if self.recording:
                raise RuntimeError("Already recording")
            self.recording, self.truncated = True, False
            self._events, self._down, self._last = [], set(), None

    def _add(self, hid: int, down: bool, now: float) -> None:
        delay = 0 if self._last is None else min(MAX_DELAY, round((now - self._last) * 1000))
        self._last = now
        self._events.append({"kind": "modifier" if is_modifier(hid) else "key", "code": hid,
                             "release": not down, "delay_ms": delay})

    def on_key(self, vk: int, down: bool, injected: bool) -> None:
        with self._lock:
            hid = VK_TO_HID.get(vk)
            if not self.recording or hid is None or (injected and not self.allow_injected):
                return
            if down:
                if hid in self._down:
                    return
                # keep room for this key's release and those stop() adds for keys still held
                if len(self._events) + len(self._down) + 2 > self.max_events:
                    self.truncated = True
                    return
                self._down.add(hid)
            elif hid not in self._down:
                return
            else:
                self._down.discard(hid)
            self._add(hid, down, self._clock())

    def stop(self) -> dict:
        with self._lock:
            if not self.recording:
                raise RuntimeError("Not recording")
            now = self._clock()
            for hid in sorted(self._down):   # never leave a key stuck down in the macro
                self._add(hid, False, now)
                self._events[-1]["delay_ms"] = 0
            self.recording = False
            return {"events": self._events, "truncated": self.truncated}


class KeyboardHook:
    """WH_KEYBOARD_LL on a dedicated thread with its own message loop."""

    def __init__(self, callback):
        self.callback = callback
        self._thread_id = None
        self._installed = False
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="cavalry-recorder", daemon=True)

    def start(self) -> None:
        self._thread.start()
        if not self._ready.wait(3):
            self.stop()   # tear down a hook that installs late
            raise RuntimeError("Couldn't start the keyboard recorder")
        if not self._installed:
            raise RuntimeError("Couldn't start the keyboard recorder")

    def stop(self) -> None:
        if self._thread_id:
            u32 = ctypes.WinDLL("user32", use_last_error=True)
            u32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
            if not u32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0):  # WM_QUIT
                log.warning("could not signal the recorder thread: %s", ctypes.get_last_error())
            self._thread.join(timeout=2)
            if self._thread.is_alive():
                log.warning("the recorder thread did not exit")

    def _run(self) -> None:
        u32, k32 = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("kernel32")
        LRESULT = ctypes.c_ssize_t
        PROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)

        class KB(ctypes.Structure):
            _fields_ = [("vk", wt.DWORD), ("scan", wt.DWORD), ("flags", wt.DWORD), ("time", wt.DWORD),
                        ("extra", ctypes.c_size_t)]

        u32.SetWindowsHookExW.argtypes = [ctypes.c_int, PROC, wt.HINSTANCE, wt.DWORD]
        u32.SetWindowsHookExW.restype = wt.HHOOK
        u32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
        u32.CallNextHookEx.restype = LRESULT
        u32.UnhookWindowsHookEx.argtypes = [wt.HHOOK]
        k32.GetModuleHandleW.restype = wt.HMODULE

        @PROC
        def proc(n, w, l):
            if n == 0 and w in (0x100, 0x101, 0x104, 0x105):
                kb = ctypes.cast(l, ctypes.POINTER(KB)).contents
                try:
                    self.callback(kb.vk, w in (0x100, 0x104), bool(kb.flags & 0x10))
                except Exception:
                    log.exception("recorder callback failed")
            return u32.CallNextHookEx(None, n, w, l)

        self._thread_id = k32.GetCurrentThreadId()
        hook = u32.SetWindowsHookExW(13, proc, k32.GetModuleHandleW(None), 0)
        self._installed = bool(hook)
        self._ready.set()
        if not hook:
            log.error("SetWindowsHookEx failed: %s", ctypes.get_last_error())
            return
        msg = wt.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u32.DispatchMessageW(ctypes.byref(msg))
        u32.UnhookWindowsHookEx(hook)
