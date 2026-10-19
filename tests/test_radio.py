import pytest

from engine.links.base import NotSupported, SizeGuardError
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
    link.write_macros(bytes([7]) * 4096)
    assert kb.state.macros == bytes([7]) * 4096
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
