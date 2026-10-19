import pytest

from engine.links.base import SizeGuardError
from engine.links.wired import WiredLink
from tests.fakes import FakeKeyboard


@pytest.fixture
def kb(fixture_blocks):
    return FakeKeyboard(fixture_blocks)


def test_reads_everything(kb, fixture_blocks):
    link = WiredLink(kb.feature_device())
    assert link.identify() == bytes.fromhex("03000000007b")
    s = link.read_all()
    assert s.config == fixture_blocks["config"]
    assert s.layers == fixture_blocks["layers"]
    assert s.palette == fixture_blocks["palette"] and len(s.palette) == 483


def test_header_format(kb):
    link = WiredLink(kb.feature_device())
    link.read_layer(1)
    assert kb.sent[-1][:8] == bytes([6, 0x83, 1, 0, 1, 0, 0xF8, 0x01])


def test_writes_and_macro_packets(kb):
    link = WiredLink(kb.feature_device())
    new = bytes([1]) * 4096
    link.write_macros(new)
    hdrs = [p[:8] for p in kb.sent[-8:]]
    assert hdrs == [bytes([6, 5, 0, 0, 8, i, 0, 2]) for i in range(8)]
    assert kb.state.macros == new
    link.write_layer(2, bytes(504))
    assert kb.state.layers[2] == bytes(504)


def test_guards(kb):
    link = WiredLink(kb.feature_device())
    for call, n in [(link.write_config, 127), (lambda b: link.write_layer(0, b), 503),
                    (link.write_macros, 4095), (link.write_key_colors, 377),
                    (link.write_palette, 484)]:
        with pytest.raises(SizeGuardError):
            call(bytes(n))
    assert kb.sent == []


def test_config_signature_guard(kb, fixture_blocks):
    link = WiredLink(kb.feature_device())
    bad = bytes(fixture_blocks["config"][:126]) + b"\0\0"
    with pytest.raises(SizeGuardError):
        link.write_config(bad)
