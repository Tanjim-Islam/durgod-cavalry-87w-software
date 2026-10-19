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
