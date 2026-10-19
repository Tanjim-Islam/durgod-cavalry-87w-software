import pytest

from engine.codec.macro import (
    Macro, MacroError, MacroEvent, decode_macro, decode_macros, encode_macro, encode_macros,
    macro_from_dict, macro_to_dict, tap,
)

# Bytes proven on the real keyboard (Shift+F15 macro fired on a keypress).
PROVEN = bytes.fromhex("0c000b00" "17000b00" "22001300"
                       "025400" "00001068" "80001068"
                       "025400" "00001069" "80001069"
                       "025400" "100010e1" "0000106a" "8000106a" "900010e1")


def proven_macros():
    return [Macro("T", tap(0x68)), Macro("T", tap(0x69)),
            Macro("T", [MacroEvent("modifier", 0xE1, delay_ms=16), *tap(0x6A),
                        MacroEvent("modifier", 0xE1, release=True, delay_ms=16)])]


def test_matches_proven_bytes():
    buf = encode_macros(proven_macros())
    assert len(buf) == 4096
    assert buf[:len(PROVEN)] == PROVEN
    assert not any(buf[len(PROVEN):])


def test_round_trip():
    ms = proven_macros() + [Macro("Mouse", [MacroEvent("mouse_button", 1, delay_ms=0x12345),
                                            MacroEvent("mouse_button", 1, release=True),
                                            MacroEvent("wheel", 0xFF)])]
    assert decode_macros(encode_macros(ms)) == ms


def test_empty():
    assert decode_macros(bytes(4096)) == []
    assert encode_macros([]) == bytes(4096)


def test_blob_layout():
    assert encode_macro(Macro("T", tap(0x68))) == bytes.fromhex("025400" "00001068" "80001068")


def test_limits():
    with pytest.raises(MacroError):
        encode_macro(Macro("x" * 31, []))
    with pytest.raises(MacroError):
        MacroEvent("key", 0x04, delay_ms=0x100000)
    with pytest.raises(MacroError):
        MacroEvent("laser", 1)
    with pytest.raises(MacroError):
        encode_macros([Macro("big", tap(0x04) * 600)])


def test_dict_round_trip():
    m = proven_macros()[2]
    assert macro_from_dict(macro_to_dict(m)) == m


def test_wrong_buffer_length():
    for n in (4095, 4097):
        with pytest.raises(MacroError):
            decode_macros(bytes(n))


def test_table_offset_not_multiple_of_4():
    with pytest.raises(MacroError):
        decode_macros(bytes([6, 0]) + bytes(4094))


def test_first_offset_past_buffer():
    with pytest.raises(MacroError):
        decode_macros(bytes([0x04, 0x10]) + bytes(4094))  # first = 0x1004 = 4100


def test_entry_outside_buffer():
    # one entry at offset 4 with size 4093 ends at byte 4097
    with pytest.raises(MacroError):
        decode_macros(bytes([4, 0, 0xFD, 0x0F]) + bytes(4092))


def test_zero_size_entry():
    with pytest.raises(MacroError):
        decode_macros(bytes([4, 0, 0, 0]) + bytes(4092))


@pytest.mark.parametrize("kind", [6, 7])
def test_reserved_event_kinds_rejected(kind):
    blob = bytes([0, kind << 4, 0, 0, 0x04])  # empty name, one event
    with pytest.raises(MacroError):
        decode_macros(bytes([4, 0, 5, 0]) + blob + bytes(4096 - 9))


@pytest.mark.parametrize("blob", [
    b"",                       # empty blob
    bytes([1, 0x41]),          # odd name-length byte
    bytes([4, 0x41, 0x00]),    # name runs past blob end
    bytes([0]) + bytes(5),     # event area not a multiple of 4
    bytes([2, 0x00, 0xD8]),    # lone UTF-16 surrogate
])
def test_decode_macro_rejects_malformed_blob(blob):
    with pytest.raises(MacroError):
        decode_macro(blob)


def test_single_blob_over_u16_raises_macro_error():
    with pytest.raises(MacroError):
        encode_macros([Macro("big", [MacroEvent("key", 4)] * 16400)])


@pytest.mark.parametrize("d", [
    {"events": []},                                                     # missing name
    {"name": "x"},                                                      # missing events
    {"name": "x", "events": [{"kind": "key", "code": 4, "bogus": 1}]},  # unknown event key
    {"name": "x", "events": [{"kind": "key"}]},                         # missing event key
    {"name": 5, "events": []},                                          # non-string name
    [1, 2],                                                             # not a mapping
])
def test_macro_from_dict_rejects_bad_input(d):
    with pytest.raises(MacroError):
        macro_from_dict(d)
