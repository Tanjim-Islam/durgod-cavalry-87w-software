import pytest

from engine.links.base import LinkError, NotSupported, SizeGuardError
from engine.links.radio import RadioLink, make_packet
from tests.fakes import FakeKeyboard


@pytest.fixture
def kb(fixture_blocks):
    return FakeKeyboard(fixture_blocks)


def test_packet_checksum():
    p = make_packet(0x05, 1, 0, 0, b"")
    assert p[:5] == bytes([0x13, 0x05, 1, 0, 0]) and p[19] == 0x19 and len(p) == 20


def test_identify_and_config(kb, fixture_blocks):
    link = RadioLink(kb.packet_device())
    assert link.identify() == bytes.fromhex("03000000007b")
    assert link.online() is True
    assert link.read_config() == fixture_blocks["config"]


def test_read_merges_across_retries(kb, fixture_blocks):
    link = RadioLink(kb.packet_device(drop_every=4), timeout_ms=1)
    assert link.read_config() == fixture_blocks["config"]


def test_writes(kb, fixture_blocks):
    link = RadioLink(kb.packet_device())
    cfg = bytearray(fixture_blocks["config"]); cfg[0x18] = 0
    link.write_config(bytes(cfg))
    assert kb.state.config == bytes(cfg)
    link.write_layer(1, bytes(504))
    assert kb.state.layers[1] == bytes(504)
    macros = b"".join(bytes([i]) * 512 for i in range(8))
    link.write_macros(macros)
    assert kb.state.macros == macros
    link.write_palette(bytes(483))
    assert kb.state.palette == bytes(483)


def test_write_retries_dropped_acks(kb, fixture_blocks):
    link = RadioLink(kb.packet_device(drop_every=3), timeout_ms=1)
    link.write_layer(0, bytes(504))
    assert kb.state.layers[0] == bytes(504)


def test_unsupported_reads_and_guards(kb):
    link = RadioLink(kb.packet_device())
    with pytest.raises(NotSupported):
        link.read_layer(0)
    with pytest.raises(SizeGuardError):
        link.write_palette(bytes(484))


class StaleAckDongle:
    """Loses packet 2 of a layer write and answers with an ack for packet 1 instead."""

    def __init__(self, inner, always=False):
        self.inner, self.always, self.pending, self.fired = inner, always, [], False

    def write(self, p):
        if p[1] == 0x01 and p[3] == 2 and (self.always or not self.fired):
            self.fired = True
            self.pending.append(make_packet(0x01, p[2], 1, 0, bytes(14)))
            return
        self.inner.write(p)

    def read(self, timeout_ms):
        return self.pending.pop(0) if self.pending else self.inner.read(timeout_ms)

    def close(self):
        self.inner.close()


def test_stale_ack_is_not_accepted(kb):
    link = RadioLink(StaleAckDongle(kb.packet_device()), timeout_ms=1)
    data = (bytes(range(256)) * 2)[:504]
    link.write_layer(0, data)
    assert kb.state.layers[0] == data


def test_persistent_stale_acks_raise(kb):
    link = RadioLink(StaleAckDongle(kb.packet_device(), always=True), timeout_ms=1)
    with pytest.raises(LinkError):
        link.write_layer(0, bytes(504))


class BadIndexDongle:
    def __init__(self):
        self.pending = []

    def write(self, p):
        self.pending = [bytes([0x13, p[1], 2, 5, 1, 0xAA]) + bytes(14)]

    def read(self, timeout_ms):
        return self.pending.pop(0) if self.pending else None

    def close(self):
        pass


def test_read_reply_index_out_of_range_raises_linkerror():
    link = RadioLink(BadIndexDongle(), retries=1, timeout_ms=1)
    with pytest.raises(LinkError):
        link.read_config()


def test_open_link_radio_does_not_probe(monkeypatch):
    from engine.links import detect

    class Dev:
        written = []

        def write(self, p):
            Dev.written.append(p)

        def read(self, t):
            return None

        def close(self):
            pass

    monkeypatch.setattr(detect, "HidPacketDevice", Dev)
    assert detect.open_link("radio").kind == "radio"
    assert Dev.written == []


def test_hid_errors_become_linkerror(monkeypatch):
    from engine.links import radio

    class H:
        def open_path(self, p): ...
        def write(self, b): raise OSError("gone")
        def read(self, n, t): raise OSError("gone")
        def close(self): ...

    monkeypatch.setattr(radio.hid, "enumerate", lambda *a: [{"path": b"x", "usage_page": 0xFF02}])
    monkeypatch.setattr(radio.hid, "device", lambda: H())
    dev = radio.HidPacketDevice()
    with pytest.raises(LinkError):
        dev.write(bytes(20))
    with pytest.raises(LinkError):
        dev.read(1)


def test_read_zero_timeout_never_blocks_forever():
    from engine.links import radio

    class H:
        def __init__(self):
            self.timeouts = []

        def read(self, n, t):
            self.timeouts.append(t)
            return []

    dev = radio.HidPacketDevice.__new__(radio.HidPacketDevice)
    dev._h = H()
    assert dev.read(0) is None
    assert dev._h.timeouts and dev._h.timeouts[0] >= 1


class SilentDongle:
    def __init__(self):
        self.written = []

    def write(self, p):
        self.written.append(p)

    def read(self, timeout_ms):
        return None

    def close(self):
        pass


def test_online_is_one_short_probe():
    import time
    dev = SilentDongle()
    link = RadioLink(dev)                    # full read budget would be several seconds
    t = time.monotonic()
    assert link.online() is False
    assert time.monotonic() - t < 1.0
    assert len(dev.written) == 1 and dev.written[0][1] == 0x07


def test_online_false_when_keyboard_asleep(kb):
    kb.asleep = True
    assert RadioLink(kb.packet_device(), timeout_ms=1).online() is False
    kb.asleep = False
    assert RadioLink(kb.packet_device(), timeout_ms=1).online() is True


def test_enumerate_oserror_is_no_device(monkeypatch):
    from engine.links import detect, radio, wired

    def boom(*a):
        raise OSError("hid busy")
    for mod in (detect, radio, wired):
        monkeypatch.setattr(mod.hid, "enumerate", boom)
    assert detect.detect_link_kind() is None
    with pytest.raises(LinkError):
        radio.HidPacketDevice()
    with pytest.raises(LinkError):
        detect.open_link("wired")
