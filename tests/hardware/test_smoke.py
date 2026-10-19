"""Read-only checks against the real keyboard. Run: pytest -m hardware -s"""
import pytest

from engine.codec.config import Config
from engine.codec.keymap import FnKey, Key, decode_layer
from engine.links.base import NotSupported
from engine.links.detect import detect_link_kind, open_link
from engine.protocol import MODEL_ID

pytestmark = pytest.mark.hardware


def test_real_keyboard_reads():
    kind = detect_link_kind()
    if kind is None:
        pytest.skip("keyboard not connected")
    link = open_link(kind)
    try:
        assert link.identify()[5] == MODEL_ID
        cfg = Config(link.read_config())
        print(f"\nlink={kind} effect={cfg.effect:#x} brightness={cfg.brightness()} sleep={cfg.sleep}")
        if kind == "wired":
            s = link.read_all()
            base = decode_layer(s.layers[0])
            assert base[0] == Key(0x29) and base[59] == FnKey()
        else:
            with pytest.raises(NotSupported):
                link.read_layer(0)
    finally:
        link.close()
