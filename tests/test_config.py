import pytest

from engine.codec.config import EFFECTS, Config, ConfigError


def test_round_trip(fixture_blocks):
    raw = fixture_blocks["config"]
    assert Config(raw).to_bytes() == raw


def test_reads_known_values(fixture_blocks):
    c = Config(fixture_blocks["config"])
    assert c.effect == 0x01
    assert c.brightness() == 4
    assert c.speed() == 3
    assert c.color() == 3
    assert c.direction() is False
    assert c.win_mac == "win"
    assert c.sleep == 0x0C
    assert c.debounce == 0
    assert c.game_mode is False
    assert c.link == "wired"


def test_setters_touch_only_their_bytes(fixture_blocks):
    raw = fixture_blocks["config"]
    c = Config(raw)
    c.set_brightness(1)
    c.set_speed(4)
    c.set_color(7)
    c.set_direction(True)
    c.win_mac = "mac"
    c.sleep = 0
    c.debounce = 2
    out = c.to_bytes()
    changed = {i for i in range(128) if out[i] != raw[i]}
    assert changed == {0x3A, 0x3B, 0x1A, 0x18, 0x03}
    assert out[0x3A] == 0x81 and out[0x3B] == 0x47


def test_effect_sets_game_flag(fixture_blocks):
    c = Config(fixture_blocks["config"])
    c.effect = 0x12
    assert c.game_mode is True and c.to_bytes()[0x09] == 1
    c.effect = 0x0B
    assert c.game_mode is False and c.to_bytes()[0x09] == 0


def test_rejects_bad_input(fixture_blocks):
    raw = fixture_blocks["config"]
    with pytest.raises(ConfigError):
        Config(raw[:100])
    with pytest.raises(ConfigError):
        Config(raw[:126] + b"\0\0")
    c = Config(raw)
    with pytest.raises(ConfigError):
        c.effect = 0x0E
    with pytest.raises(ConfigError):
        c.set_brightness(5)
    with pytest.raises(ConfigError):
        c.set_color(8)


def test_effect_table():
    assert len(EFFECTS) == 17
    assert EFFECTS[0] == (0x01, "Always On")
    assert EFFECTS[10] == (0x0B, "Go with the Flow")
    assert EFFECTS[-1] == (0x12, "Game Mode")
    assert 0x0E not in {i for i, _ in EFFECTS}
