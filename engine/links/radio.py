"""2.4G link through the dongle: 20-byte report 0x13 packets with a sum checksum."""
from __future__ import annotations

import time
from typing import Protocol

import hid

from ..protocol import (CONFIG_SIGNATURE, CONFIG_SIZE, KEY_COLORS_SIZE, LAYER_SIZE, MACRO_BLOCK,
                        MACRO_SIZE, PALETTE_SIZE, RADIO_PID, RADIO_VID, Radio)
from .base import Link, LinkError, NotSupported, SizeGuardError, guard


class PacketDevice(Protocol):
    def write(self, packet: bytes) -> None: ...
    def read(self, timeout_ms: int) -> bytes | None: ...
    def close(self) -> None: ...


class HidPacketDevice:
    def __init__(self):
        try:
            devices = hid.enumerate(RADIO_VID, RADIO_PID)
        except OSError as e:
            raise LinkError(f"cannot list USB devices: {e}") from e
        path = next((d["path"] for d in devices if d["usage_page"] == 0xFF02), None)
        if path is None:
            raise LinkError("2.4G dongle not found")
        self._h = hid.device()
        try:
            self._h.open_path(path)
        except OSError as e:
            raise LinkError(f"cannot open dongle: {e}") from e

    def write(self, packet: bytes) -> None:
        try:
            n = self._h.write(list(packet))
        except OSError as e:
            raise LinkError(f"dongle write failed: {e}") from e
        if n < 0:
            raise LinkError("dongle write failed")

    def read(self, timeout_ms: int) -> bytes | None:
        try:
            r = self._h.read(Radio.PACKET_SIZE, max(timeout_ms, 1))
        except OSError as e:
            raise LinkError(f"dongle read failed: {e}") from e
        return bytes(r) if r else None

    def close(self) -> None:
        try:
            self._h.close()
        except OSError as e:
            raise LinkError(f"dongle close failed: {e}") from e


def make_packet(cmd: int, total: int, index: int, sub: int, data: bytes) -> bytes:
    if len(data) > Radio.CHUNK or sub > 0x0F:
        raise ValueError("bad radio packet")
    p = bytearray([Radio.REPORT_ID, cmd, total, index, (sub << 4) | len(data)]) + data
    p += bytes(Radio.PACKET_SIZE - len(p))
    p[19] = sum(p[:19]) & 0xFF
    return bytes(p)


class RadioLink(Link):
    kind = "radio"
    PROBE_MS = 150

    def __init__(self, dev: PacketDevice, retries: int = 5, timeout_ms: int = 500):
        self.dev, self.retries, self.timeout_ms = dev, retries, timeout_ms

    def _check(self, cmd: int) -> None:
        if cmd not in Radio.ALLOWED:
            raise LinkError(f"radio command {cmd:#x} is not whitelisted")

    def _drain(self, timeout_ms: int) -> None:
        deadline = time.monotonic() + max(timeout_ms, 100) / 1000
        while time.monotonic() < deadline and self.dev.read(0):
            pass

    def _recv(self, cmd: int, ack: tuple[int, int] | None = None,
              timeout_ms: int | None = None) -> bytes | None:
        """Next reply to cmd; with ack=(total, index), only a matching write ack counts."""
        timeout_ms = self.timeout_ms if timeout_ms is None else timeout_ms
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            r = self.dev.read(timeout_ms)
            if r is None:
                return None
            if r[0] == Radio.REPORT_ID and (r[1] & 0x7F) == cmd:
                if ack is None or (not r[1] & 0x80 and (r[2], r[3]) == ack):
                    return r
            if time.monotonic() >= deadline:
                return None

    def _try_read(self, cmd: int, size: int, attempts: int, timeout_ms: int) -> bytes | None:
        self._check(cmd)
        got: dict[int, bytes] = {}
        total = None
        for _ in range(attempts):
            self._drain(timeout_ms)
            self.dev.write(make_packet(cmd, 1, 0, 0, b""))
            for _ in range(0x80):
                r = self._recv(cmd, timeout_ms=timeout_ms)
                if r is None or (r[1] & 0x80):
                    break
                n = r[2] & 0x7F
                if r[3] >= n or (total and n != total):
                    got.clear()
                    total = None
                    break
                total = n
                got[r[3]] = r[5:5 + min(r[4] & 0x0F, Radio.CHUNK)]
                if r[3] + 1 >= total:
                    break
            if total and len(got) == total:
                data = b"".join(got[i] for i in range(total))
                if len(data) >= size:
                    return data[:size]
        return None

    def _read(self, cmd: int, size: int) -> bytes:
        data = self._try_read(cmd, size, self.retries + 3, self.timeout_ms)
        if data is None:
            raise LinkError(f"incomplete reply to {cmd:#x}")
        return data

    def _write(self, cmd: int, data: bytes, sub: int = 0) -> None:
        self._check(cmd)
        chunks = [data[i:i + Radio.CHUNK] for i in range(0, len(data), Radio.CHUNK)]
        for i, c in enumerate(chunks):
            for _ in range(self.retries):
                self._drain(self.timeout_ms)
                self.dev.write(make_packet(cmd, len(chunks), i, sub, c))
                if self._recv(cmd, ack=(len(chunks), i)):
                    break
            else:
                raise LinkError(f"no ack for {cmd:#x} packet {i}")

    def identify(self) -> bytes:
        return self._read(Radio.IDENTIFY, 10)[:6]

    def online(self) -> bool:
        """One short probe: is the keyboard awake and paired? No reply counts as no."""
        timeout = min(self.timeout_ms, self.PROBE_MS)
        return self._try_read(Radio.ONLINE, 1, 1, timeout) == b"\x01"

    def read_config(self) -> bytes:
        return self._read(Radio.READ_CONFIG, CONFIG_SIZE)

    def write_config(self, raw: bytes) -> None:
        guard("config", raw, CONFIG_SIZE)
        if raw[0x7E:0x80] != CONFIG_SIGNATURE:
            raise SizeGuardError("refusing to send config without 5a a5 signature")
        self._write(Radio.WRITE_CONFIG, raw)

    def write_layer(self, n: int, raw: bytes) -> None:
        if n not in range(4):
            raise SizeGuardError(f"bad layer {n}")
        self._write(Radio.WRITE_LAYER, guard("layer", raw, LAYER_SIZE), sub=n)

    def write_macros(self, raw: bytes) -> None:
        guard("macros", raw, MACRO_SIZE)
        for i in range(MACRO_SIZE // MACRO_BLOCK):
            self._write(Radio.WRITE_MACROS, raw[i * MACRO_BLOCK:(i + 1) * MACRO_BLOCK], sub=i)

    def write_key_colors(self, raw: bytes) -> None:
        self._write(Radio.WRITE_KEY_COLORS, guard("key_colors", raw, KEY_COLORS_SIZE))

    def write_palette(self, raw: bytes) -> None:
        self._write(Radio.WRITE_PALETTE, guard("palette", raw, PALETTE_SIZE))

    def _no_read(self, *_):
        raise NotSupported("this block can't be read over 2.4G")

    read_layer = read_macros = read_key_colors = read_palette = _no_read

    def close(self) -> None:
        self.dev.close()
