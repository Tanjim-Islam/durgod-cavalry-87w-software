import pytest

from engine.codec.macro import (
    Macro, MacroError, MacroEvent, decode_macros, encode_macro, encode_macros,
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
