"""2.4G link through the dongle: 20-byte report 0x13 packets with a sum checksum."""
from __future__ import annotations

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
        path = next((d["path"] for d in hid.enumerate(RADIO_VID, RADIO_PID)
                     if d["usage_page"] == 0xFF02), None)
        if path is None:
            raise LinkError("2.4G dongle not found")
        self._h = hid.device()
        self._h.open_path(path)

    def write(self, packet: bytes) -> None:
        if self._h.write(list(packet)) < 0:
            raise LinkError("dongle write failed")

    def read(self, timeout_ms: int) -> bytes | None:
        r = self._h.read(Radio.PACKET_SIZE, timeout_ms)
        return bytes(r) if r else None

    def close(self) -> None:
        self._h.close()


def make_packet(cmd: int, total: int, index: int, sub: int, data: bytes) -> bytes:
    if len(data) > Radio.CHUNK or sub > 0x0F:
        raise ValueError("bad radio packet")
    p = bytearray([Radio.REPORT_ID, cmd, total, index, (sub << 4) | len(data)]) + data
    p += bytes(Radio.PACKET_SIZE - len(p))
    p[19] = sum(p[:19]) & 0xFF
    return bytes(p)


class RadioLink(Link):
    kind = "radio"

    def __init__(self, dev: PacketDevice, retries: int = 5, timeout_ms: int = 500):
        self.dev, self.retries, self.timeout_ms = dev, retries, timeout_ms

    def _check(self, cmd: int) -> None:
        if cmd not in Radio.ALLOWED:
            raise LinkError(f"radio command {cmd:#x} is not whitelisted")

    def _drain(self) -> None:
        while self.dev.read(0):
            pass

    def _recv(self, cmd: int) -> bytes | None:
        while True:
            r = self.dev.read(self.timeout_ms)
            if r is None:
                return None
            if r[0] == Radio.REPORT_ID and (r[1] & 0x7F) == cmd:
                return r

    def _read(self, cmd: int, size: int) -> bytes:
        self._check(cmd)
        got: dict[int, bytes] = {}
        total = None
        for _ in range(self.retries + 3):
            self._drain()
            self.dev.write(make_packet(cmd, 1, 0, 0, b""))
            while True:
                r = self._recv(cmd)
                if r is None or (r[1] & 0x80):
                    break
                total = r[2] & 0x7F
                got[r[3]] = r[5:5 + min(r[4] & 0x0F, Radio.CHUNK)]
                if r[3] + 1 >= total:
                    break
            if total and len(got) == total:
                data = b"".join(got[i] for i in range(total))
                if len(data) >= size:
                    return data[:size]
        raise LinkError(f"incomplete reply to {cmd:#x}")

    def _write(self, cmd: int, data: bytes, sub: int = 0) -> None:
        self._check(cmd)
        chunks = [data[i:i + Radio.CHUNK] for i in range(0, len(data), Radio.CHUNK)]
        for i, c in enumerate(chunks):
            for _ in range(self.retries):
                self._drain()
                self.dev.write(make_packet(cmd, len(chunks), i, sub, c))
                if self._recv(cmd):
                    break
            else:
                raise LinkError(f"no ack for {cmd:#x} packet {i}")

    def identify(self) -> bytes:
        return self._read(Radio.IDENTIFY, 10)[:6]

    def online(self) -> bool:
        return self._read(Radio.ONLINE, 1) == b"\x01"

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
