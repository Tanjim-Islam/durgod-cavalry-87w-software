"""In-memory Cavalry 87W that speaks both the wired and the 2.4G protocol."""
from __future__ import annotations

from engine.codec.snapshot import Snapshot
from engine.links.base import LinkError

R_CONFIG, R_LAYER, R_MACROS, R_COLORS, R_PALETTE = 0x84, 0x83, 0x85, 0x86, 0x8A


class FakeKeyboard:
    def __init__(self, blocks: dict):
        self.state = Snapshot(blocks["config"], list(blocks["layers"]), blocks["macros"],
                              blocks["key_colors"], blocks["palette"])
        self.identity = blocks["identity"]
        self.sent: list[bytes] = []
        self.connected = True
        self.fail_on_write = False
        self.asleep = False          # 2.4G: dongle answers "offline", keyboard answers nothing
        self.link_byte = None        # when set, firmware owns config 0x0E and forces this value
        self._macro_buf = bytearray(self.state.macros)

    # ---------- wired: feature report 6 ----------
    def feature_device(self):
        kb = self

        class Dev:
            reply = b""

            def set_feature(self, data: bytes) -> None:
                if not kb.connected:
                    raise LinkError("unplugged")
                if kb.fail_on_write and data[1] < 0x80:
                    raise LinkError("unplugged mid-write")
                kb.sent.append(bytes(data))
                assert len(data) == 520 and data[0] == 6
                Dev.reply = kb._wired(data)

            def get_feature(self, report_id: int, size: int) -> bytes:
                if not kb.connected:
                    raise LinkError("unplugged")
                return Dev.reply

            def close(self) -> None:
                pass

        return Dev()

    def _wired(self, d: bytes) -> bytes:
        cmd, sub, count, index = d[1], d[2], d[4], d[5]
        size = d[6] | d[7] << 8
        body, s = d[8:8 + size], self.state
        out = bytearray(d[:8]) + bytearray(512)
        if cmd == 0x82:
            out[8:14] = self.identity
        elif cmd == R_CONFIG:
            out[8:136] = s.config
        elif cmd == 0x04:
            s.config = self._own_link_byte(bytes(body))
        elif cmd == R_LAYER:
            out[8:512] = s.layers[sub]
        elif cmd == 0x03:
            s.layers[sub] = bytes(body)
        elif cmd == R_MACROS:
            out[8:520] = s.macros[index * 512:(index + 1) * 512]
        elif cmd == 0x05:
            self._macro_buf[index * 512:(index + 1) * 512] = body
            s.macros = bytes(self._macro_buf)
        elif cmd == R_COLORS:
            out[8:8 + 378] = s.key_colors
        elif cmd == 0x06:
            s.key_colors = bytes(body)
        elif cmd == R_PALETTE:
            out[8:8 + 483] = s.palette
            out[8 + 483:8 + 489] = self.identity
        elif cmd == 0x0A:
            s.palette = bytes(body)
        else:
            raise AssertionError(f"fake keyboard got non-whitelisted command {cmd:#x}")
        if cmd < 0x80:
            return bytes([4, 4, 4, 4, 4, 4, 0x5A, 0xA5]) + bytes(512)
        return bytes(out)

    def _own_link_byte(self, cfg: bytes) -> bytes:
        if self.link_byte is None:
            return cfg
        return cfg[:0x0E] + bytes([self.link_byte]) + cfg[0x0F:]

    # ---------- radio: report 0x13 packets ----------
    def packet_device(self, drop_every: int = 0):
        kb = self

        class Dev:
            queue: list[bytes] = []
            n = 0
            partial: dict = {}

            def write(self, p: bytes) -> None:
                if not kb.connected:
                    raise LinkError("dongle lost keyboard")
                assert len(p) == 20 and p[0] == 0x13 and p[19] == sum(p[:19]) & 0xFF
                kb.sent.append(bytes(p))
                Dev.queue += kb._radio(p, Dev.partial)

            def read(self, timeout_ms: int):
                while Dev.queue:
                    pkt = Dev.queue.pop(0)
                    Dev.n += 1
                    if drop_every and Dev.n % drop_every == 0:
                        continue
                    return pkt
                return None

            def close(self) -> None:
                pass

        return Dev()

    def _radio(self, p: bytes, partial: dict) -> list[bytes]:
        cmd, total, index, sub, n = p[1], p[2], p[3], p[4] >> 4, p[4] & 0x0F
        s = self.state

        def reply(data: bytes) -> list[bytes]:
            chunks = [data[i:i + 14] for i in range(0, len(data), 14)]
            out = []
            for i, c in enumerate(chunks):
                q = bytearray([0x13, cmd, len(chunks), i, len(c)]) + c + bytes(14 - len(c)) + b"\0"
                q[19] = sum(q[:19]) & 0xFF
                out.append(bytes(q))
            return out

        if cmd == 0x07:
            return reply(b"\x00" if self.asleep else b"\x01")
        if self.asleep:
            return []
        if cmd == 0x05:
            return reply(self.identity + b"\x01\0\0\0")
        if cmd == 0x44:
            return reply(s.config)
        key = (cmd, sub)
        if index == 0:
            partial[key] = {}
        buf = partial.setdefault(key, {})
        buf[index] = p[5:5 + n]
        if len(buf) == total:
            data = b"".join(buf[i] for i in range(total))
            del partial[key]
            if cmd == 0x04:
                s.config = self._own_link_byte(data)
            elif cmd == 0x01:
                s.layers[sub] = data
            elif cmd == 0x02:
                s.key_colors = data
            elif cmd == 0x03:
                self._macro_buf[sub * 512:(sub + 1) * 512] = data
                s.macros = bytes(self._macro_buf)
            elif cmd == 0x09:
                s.palette = data
            else:
                raise AssertionError(f"fake keyboard got non-whitelisted radio command {cmd:#x}")
        ack = bytearray(p)
        return [bytes(ack)]
