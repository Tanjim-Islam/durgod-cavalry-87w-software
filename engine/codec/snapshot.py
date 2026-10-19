"""All writable blocks of the keyboard in one object."""
from __future__ import annotations

from dataclasses import dataclass

from ..protocol import (CONFIG_SIGNATURE, CONFIG_SIZE, KEY_COLORS_SIZE, LAYER_COUNT, LAYER_SIZE,
                        MACRO_SIZE, PALETTE_SIZE)

BLOCKS = ["config", "layer0", "layer1", "layer2", "layer3", "macros", "key_colors", "palette"]


class SnapshotError(ValueError):
    pass


def _hex(v) -> bytes:
    if not isinstance(v, str):
        raise SnapshotError(f"expected a hex string, got {type(v).__name__}")
    try:
        return bytes.fromhex(v)
    except ValueError as e:
        raise SnapshotError(f"bad hex: {e}") from e


def _field(d: dict, key: str):
    if key not in d:
        raise SnapshotError(f"missing {key}")
    return d[key]


@dataclass
class Snapshot:
    config: bytes
    layers: list[bytes]
    macros: bytes
    key_colors: bytes
    palette: bytes

    def block(self, name: str) -> bytes:
        if name not in BLOCKS:
            raise SnapshotError(f"unknown block {name!r}")
        return self.layers[int(name[-1])] if name.startswith("layer") else getattr(self, name)

    def validate(self) -> None:
        sizes = {"config": CONFIG_SIZE, "macros": MACRO_SIZE, "key_colors": KEY_COLORS_SIZE,
                 "palette": PALETTE_SIZE}
        for k, n in sizes.items():
            v = getattr(self, k)
            if not isinstance(v, bytes) or len(v) != n:
                raise SnapshotError(f"{k} must be {n} bytes")
        if not isinstance(self.layers, list) or len(self.layers) != LAYER_COUNT:
            raise SnapshotError(f"need {LAYER_COUNT} layers")
        for i, x in enumerate(self.layers):
            if not isinstance(x, bytes) or len(x) != LAYER_SIZE:
                raise SnapshotError(f"layer{i} must be {LAYER_SIZE} bytes")
        if self.config[0x7E:0x80] != CONFIG_SIGNATURE:
            raise SnapshotError("config signature missing")

    def copy(self) -> "Snapshot":
        return Snapshot(self.config, list(self.layers), self.macros, self.key_colors, self.palette)

    def changed_blocks(self, other: "Snapshot") -> list[str]:
        return [b for b in BLOCKS if self.block(b) != other.block(b)]

    def to_json(self) -> dict:
        return {"config": self.config.hex(), "layers": [x.hex() for x in self.layers],
                "macros": self.macros.hex(), "key_colors": self.key_colors.hex(),
                "palette": self.palette.hex()}

    @classmethod
    def from_json(cls, d: dict) -> "Snapshot":
        if not isinstance(d, dict):
            raise SnapshotError("snapshot must be a JSON object")
        layers = _field(d, "layers")
        if not isinstance(layers, list):
            raise SnapshotError("layers must be a list")
        s = cls(_hex(_field(d, "config")), [_hex(x) for x in layers],
                _hex(_field(d, "macros")), _hex(_field(d, "key_colors")),
                _hex(_field(d, "palette")))
        s.validate()
        return s
