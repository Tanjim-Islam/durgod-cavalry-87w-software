"""Common link interface and size guard."""
from __future__ import annotations

import abc

from ..codec.snapshot import Snapshot
from ..protocol import LAYER_COUNT


class LinkError(IOError):
    pass


class NotSupported(LinkError):
    pass


class SizeGuardError(ValueError):
    pass


def guard(name: str, data: bytes, size: int) -> bytes:
    if len(data) != size:
        raise SizeGuardError(f"refusing to send {name}: {len(data)} bytes, must be {size}")
    return bytes(data)


class Link(abc.ABC):
    kind: str = ""

    @abc.abstractmethod
    def identify(self) -> bytes: ...
    @abc.abstractmethod
    def read_config(self) -> bytes: ...
    @abc.abstractmethod
    def write_config(self, raw: bytes) -> None: ...
    @abc.abstractmethod
    def read_layer(self, n: int) -> bytes: ...
    @abc.abstractmethod
    def write_layer(self, n: int, raw: bytes) -> None: ...
    @abc.abstractmethod
    def read_macros(self) -> bytes: ...
    @abc.abstractmethod
    def write_macros(self, raw: bytes) -> None: ...
    @abc.abstractmethod
    def read_key_colors(self) -> bytes: ...
    @abc.abstractmethod
    def write_key_colors(self, raw: bytes) -> None: ...
    @abc.abstractmethod
    def read_palette(self) -> bytes: ...
    @abc.abstractmethod
    def write_palette(self, raw: bytes) -> None: ...
    @abc.abstractmethod
    def close(self) -> None: ...

    def read_all(self) -> Snapshot:
        s = Snapshot(self.read_config(), [self.read_layer(i) for i in range(LAYER_COUNT)],
                     self.read_macros(), self.read_key_colors(), self.read_palette())
        s.validate()
        return s

    def write_block(self, name: str, data: bytes) -> None:
        if name.startswith("layer"):
            self.write_layer(int(name[-1]), data)
        else:
            getattr(self, f"write_{name}")(data)

    def read_block(self, name: str) -> bytes:
        if name.startswith("layer"):
            return self.read_layer(int(name[-1]))
        return getattr(self, f"read_{name}")()
