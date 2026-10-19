import pytest

from engine.codec.colors import (
    DEFAULT_PALETTE_GROUP, ColorError, decode_key_colors, decode_palette, encode_key_colors,
    encode_palette,
)
from engine.codec.snapshot import Snapshot, SnapshotError


def snap(b):
    return Snapshot(b["config"], list(b["layers"]), b["macros"], b["key_colors"], b["palette"])


def test_key_colors_round_trip(fixture_blocks):
    raw = fixture_blocks["key_colors"]
    cols = decode_key_colors(raw)
    assert len(cols) == 126
    assert cols[0] == (0, 0, 0xFF)          # Esc is blue in Game Mode
    assert encode_key_colors(cols) == raw


def test_palette_round_trip(fixture_blocks):
    raw = fixture_blocks["palette"]
    groups = decode_palette(raw)
    assert len(groups) == 23 and all(g == DEFAULT_PALETTE_GROUP for g in groups)
    assert encode_palette(groups) == raw and len(raw) == 483


def test_color_validation():
    with pytest.raises(ColorError):
        encode_key_colors([(0, 0, 0)] * 125)
    with pytest.raises(ColorError):
        encode_palette([DEFAULT_PALETTE_GROUP] * 24)
    with pytest.raises(ColorError):
        encode_key_colors([(256, 0, 0)] * 126)


def test_snapshot_json_and_diff(fixture_blocks):
    s = snap(fixture_blocks)
    s.validate()
    t = Snapshot.from_json(s.to_json())
    assert t.to_json() == s.to_json()
    u = s.copy()
    u.layers[1] = bytes(504)
    u.palette = bytes(483)
    assert s.changed_blocks(u) == ["layer1", "palette"]
    assert s.layers[1] != u.layers[1]


def test_snapshot_rejects_bad_sizes(fixture_blocks):
    s = snap(fixture_blocks)
    s.palette = bytes(484)
    with pytest.raises(SnapshotError):
        s.validate()


# Malformed input must raise ColorError / SnapshotError, never TypeError/ValueError/KeyError.

@pytest.mark.parametrize("bad", [
    None, 5, [0] * 126, [(0, 0)] * 126, [(0, 0, 0, 0)] * 126, [(True, 0, 0)] * 126,
    [(1.0, 0, 0)] * 126, [("a", 0, 0)] * 126, [(0, 0, 0)] * 125,
])
def test_encode_key_colors_rejects_malformed(bad):
    with pytest.raises(ColorError):
        encode_key_colors(bad)


def test_encode_palette_rejects_malformed():
    bad_group = [(True, 0, 0)] + DEFAULT_PALETTE_GROUP[1:]
    for bad in (None, [DEFAULT_PALETTE_GROUP] * 22, [None] * 23,
                [DEFAULT_PALETTE_GROUP[:6]] * 23, [bad_group] + [DEFAULT_PALETTE_GROUP] * 22):
        with pytest.raises(ColorError):
            encode_palette(bad)


@pytest.mark.parametrize("raw", [None, [0] * 378, bytes(377), bytes(379)])
def test_decode_key_colors_rejects_malformed(raw):
    with pytest.raises(ColorError):
        decode_key_colors(raw)


@pytest.mark.parametrize("raw", [None, [0] * 483, bytes(482), bytes(484)])
def test_decode_palette_rejects_malformed(raw):
    with pytest.raises(ColorError):
        decode_palette(raw)


def test_block_rejects_unknown_name(fixture_blocks):
    with pytest.raises(SnapshotError):
        snap(fixture_blocks).block("layer9")


@pytest.mark.parametrize("field,value", [
    ("config", None), ("config", [0] * 128), ("macros", 4096), ("key_colors", None),
    ("palette", "x" * 483), ("layers", None), ("layers", "abcd"),
    ("layers", [bytes(504)] * 3), ("layers", [bytes(504)] * 3 + [None]),
    ("layers", [bytes(504)] * 3 + ["x" * 504]),
])
def test_validate_rejects_wrong_block_types(fixture_blocks, field, value):
    s = snap(fixture_blocks)
    setattr(s, field, value)
    with pytest.raises(SnapshotError):
        s.validate()


@pytest.mark.parametrize("key", ["config", "layers", "macros", "key_colors", "palette"])
def test_from_json_rejects_missing_key(fixture_blocks, key):
    d = snap(fixture_blocks).to_json()
    del d[key]
    with pytest.raises(SnapshotError):
        Snapshot.from_json(d)


@pytest.mark.parametrize("key,value", [
    ("macros", "zz"), ("macros", "abc"), ("config", 12), ("palette", None),
    ("layers", "abcd"), ("layers", None), ("layers", [1, 2, 3, 4]), ("layers", [None] * 4),
    ("key_colors", "0"),
])
def test_from_json_rejects_bad_values(fixture_blocks, key, value):
    d = snap(fixture_blocks).to_json()
    d[key] = value
    with pytest.raises(SnapshotError):
        Snapshot.from_json(d)


@pytest.mark.parametrize("d", [None, [], "snapshot"])
def test_from_json_rejects_non_object(d):
    with pytest.raises(SnapshotError):
        Snapshot.from_json(d)
