import pytest

from engine.shell.recorder import Recorder
from engine.shell.vkmap import VK_TO_HID, is_modifier


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


def test_vk_map_basics():
    assert VK_TO_HID[0x41] == 0x04 and VK_TO_HID[0x5A] == 0x1D       # A, Z
    assert VK_TO_HID[0x31] == 0x1E and VK_TO_HID[0x30] == 0x27       # 1, 0
    assert VK_TO_HID[0x70] == 0x3A and VK_TO_HID[0x87] == 0x73       # F1, F24
    assert VK_TO_HID[0xA0] == 0xE1 and is_modifier(0xE1)             # Left Shift
    assert not is_modifier(0x04)


def test_records_taps_with_delays_and_skips_repeats_and_injected():
    c = Clock(); r = Recorder(clock=c)
    r.start()
    r.on_key(0x48, True, False)            # H down at 0
    c.t = 0.05; r.on_key(0x48, True, False)  # auto-repeat: ignored
    c.t = 0.08; r.on_key(0x48, False, False)
    c.t = 0.20; r.on_key(0x49, True, True)   # injected: ignored
    c.t = 0.30; r.on_key(0xA0, True, False)  # Left Shift down
    c.t = 0.35; r.on_key(0xFF, True, False)  # unmapped: ignored
    out = r.stop()
    assert out["truncated"] is False
    assert out["events"] == [
        {"kind": "key", "code": 0x0B, "release": False, "delay_ms": 0},
        {"kind": "key", "code": 0x0B, "release": True, "delay_ms": 80},
        {"kind": "modifier", "code": 0xE1, "release": False, "delay_ms": 220},
        {"kind": "modifier", "code": 0xE1, "release": True, "delay_ms": 0},   # auto-released on stop
    ]
    assert r.recording is False


def test_truncates_at_max_events():
    c = Clock(); r = Recorder(clock=c, max_events=3)
    r.start()
    for i in range(5):
        c.t += 0.01; r.on_key(0x41 + i, True, False)
    out = r.stop()
    assert out["truncated"] is True
    assert sum(1 for e in out["events"] if not e["release"]) == 3


def test_start_twice_and_stop_without_start():
    r = Recorder()
    with pytest.raises(RuntimeError):
        r.stop()
    r.start()
    with pytest.raises(RuntimeError):
        r.start()
