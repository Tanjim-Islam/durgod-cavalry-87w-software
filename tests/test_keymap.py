import pytest

from engine.codec.keymap import (
    KEY_SLOTS, SLOT_BY_NAME, Consumer, FnKey, Key, KeymapError, Lighting, MacroRef, Mouse,
    NoAction, Raw, System, action_from_dict, action_to_dict, decode_entry, decode_layer,
    encode_entry, encode_layer, wired_unsafe,
)


def test_layers_round_trip(fixture_blocks):
    for raw in fixture_blocks["layers"]:
        assert encode_layer(decode_layer(raw)) == raw


@pytest.mark.parametrize("hexs,action", [
    ("00000000", NoAction()),
    ("00000029", Key(0x29)),
    ("00020000", Key(0, mods=0x02)),
    ("00011d00", Key(0x1D, mods=0x01, high=True)),
    ("0d000000", FnKey()),
    ("020000e2", Consumer(0x00E2)),
    ("02000223", Consumer(0x0223)),
    ("03010100", MacroRef(0)),
    ("03020102", MacroRef(2, mode=2, count=1)),
    ("07000016", System(0x16)),
    ("08030100", Lighting(3, 1)),
    ("01010100", Mouse(1)),
    ("aabbccdd", Raw(bytes.fromhex("aabbccdd"))),
])
def test_entry_round_trip(hexs, action):
    raw = bytes.fromhex(hexs)
    assert decode_entry(raw) == action
    assert encode_entry(action) == raw


def test_base_layer_names(fixture_blocks):
    base = decode_layer(fixture_blocks["layers"][0])
    assert base[SLOT_BY_NAME["Esc"]] == Key(0x29)
    assert base[SLOT_BY_NAME["J"]] == Key(0x0D)
    assert base[SLOT_BY_NAME["Fn"]] == FnKey()
    assert KEY_SLOTS[45] == "J" and KEY_SLOTS[96] == "Pause"
    assert len(KEY_SLOTS) == 90


def test_dict_round_trip():
    for a in [NoAction(), Key(0x68, mods=0x02), Consumer(0x192), MacroRef(1, 4, 1),
              System(0x01), Lighting(0), FnKey(), Mouse(3), Raw(b"\x0e\x00\x00\x00")]:
        assert action_from_dict(action_to_dict(a)) == a


def test_validation():
    with pytest.raises(KeymapError):
        encode_layer([NoAction()] * 125)
    with pytest.raises(KeymapError):
        encode_entry(Key(0x100))
    with pytest.raises(KeymapError):
        action_from_dict({"type": "nope"})


def test_wired_unsafe():
    assert wired_unsafe(Key(0x73)) is True
    assert wired_unsafe(Key(0x70)) is False
    assert wired_unsafe(Consumer(0xE2)) is False


@pytest.mark.parametrize("hexs", [
    "02000000", "01000000", "03000000", "07000100", "0d000001", "02ffff00",
    "07000000", "08000000", "00ff0000", "00010101", "03010000", "ffffffff",
])
def test_boundary_entries_round_trip(hexs):
    raw = bytes.fromhex(hexs)
    assert encode_entry(decode_entry(raw)) == raw


def test_every_decodable_entry_round_trips():
    values = (0x00, 0x01, 0x02, 0x03, 0x04, 0x07, 0x08, 0x0D, 0xFF)
    for t in range(16):
        for b1 in values:
            for b2 in values:
                for b3 in values:
                    raw = bytes([t, b1, b2, b3])
                    assert encode_entry(decode_entry(raw)) == raw, raw.hex()


def test_zero_payload_entries_fall_to_raw():
    for hexs in ("02000000", "01000000", "03000000", "07000100"):
        assert decode_entry(bytes.fromhex(hexs)) == Raw(bytes.fromhex(hexs))


@pytest.mark.parametrize("d", [
    None,
    {},
    {"type": ["x"]},
    {"type": "raw"},
    {"type": "raw", "data": "zz"},
    {"type": "raw", "data": 5},
    {"type": "raw", "data": "aabb"},
    {"type": "key"},
    {"type": "key", "hid": "4"},
    {"type": "key", "hid": 1.5},
    {"type": "key", "hid": 4, "bogus": 1},
    {"type": "key", "hid": 0x100},
    {"type": "key", "hid": 4, "high": "yes"},
    {"type": "consumer", "usage": 0},
])
def test_malformed_dict_raises_keymap_error(d):
    with pytest.raises(KeymapError):
        action_from_dict(d)


def test_encode_rejects_wrong_types():
    bad = [Key(1.5), Key("4"), Key(True), Key(4, high="yes"), Mouse("1"), Consumer("4"),
           Consumer(1.5), MacroRef(0, mode=1.0), MacroRef(0, count="1"), System(None),
           Lighting(1.0), Raw("abcd"), Raw(b"\x01\x02\x03")]
    for a in bad:
        with pytest.raises(KeymapError):
            encode_entry(a)


def test_action_to_dict_rejects_unknown_type():
    with pytest.raises(KeymapError):
        action_to_dict(object())
