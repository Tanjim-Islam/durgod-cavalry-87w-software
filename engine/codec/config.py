"""128-byte config block (cmd 0x84/0x04 wired, 0x44/0x04 radio)."""
from __future__ import annotations

from ..protocol import CONFIG_SIGNATURE, CONFIG_SIZE

EFFECTS: tuple[tuple[int, str], ...] = (
    (0x01, "Always On"), (0x02, "Breathing"), (0x03, "Dream Rainbow"),
    (0x04, "Hair Trigger"), (0x05, "Walk in the Rain"), (0x06, "Rainbow Roulette"),
    (0x07, "Key Ripples"), (0x08, "The Stars"), (0x09, "Step on the Snow"),
    (0x0A, "Continuous Flow"), (0x0B, "Go with the Flow"), (0x0C, "Like a Shadow"),
    (0x0D, "Blinding Light Waves"), (0x0F, "Spin the Windmill"),
    (0x10, "Colourful Waterfalls"), (0x11, "Flower Bloom"), (0x12, "Game Mode"),
)
EFFECT_IDS = frozenset(i for i, _ in EFFECTS)
GAME_MODE = 0x12
COLOR_MULTI = 7

OFF_DEBOUNCE, OFF_GAME, OFF_EFFECT, OFF_LINK = 0x03, 0x09, 0x0A, 0x0E
OFF_SLEEP, OFF_WINMAC, OFF_EFFECT_TABLE = 0x18, 0x1A, 0x38


class ConfigError(ValueError):
    pass


class Config:
    def __init__(self, raw: bytes):
        if len(raw) != CONFIG_SIZE:
            raise ConfigError(f"config must be {CONFIG_SIZE} bytes, got {len(raw)}")
        if bytes(raw[0x7E:0x80]) != CONFIG_SIGNATURE:
            raise ConfigError("config signature 5a a5 missing")
        self._b = bytearray(raw)

    def to_bytes(self) -> bytes:
        return bytes(self._b)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Config) and other._b == self._b

    def _pair(self, effect: int | None) -> int:
        e = self.effect if effect is None else effect
        if e not in EFFECT_IDS:
            raise ConfigError(f"unknown effect {e:#x}")
        return OFF_EFFECT_TABLE + 2 * e

    @staticmethod
    def _range(name: str, v: int, lo: int, hi: int) -> None:
        if not lo <= v <= hi:
            raise ConfigError(f"{name} must be {lo}..{hi}, got {v}")

    @property
    def effect(self) -> int:
        return self._b[OFF_EFFECT]

    @effect.setter
    def effect(self, e: int) -> None:
        if e not in EFFECT_IDS:
            raise ConfigError(f"unknown effect {e:#x}")
        self._b[OFF_EFFECT] = e
        self._b[OFF_GAME] = 1 if e == GAME_MODE else 0

    @property
    def game_mode(self) -> bool:
        return self._b[OFF_GAME] == 1

    def brightness(self, effect: int | None = None) -> int:
        return self._b[self._pair(effect)] & 0x0F

    def set_brightness(self, v: int, effect: int | None = None) -> None:
        self._range("brightness", v, 0, 4)
        a = self._pair(effect)
        self._b[a] = (self._b[a] & 0xF0) | v

    def direction(self, effect: int | None = None) -> bool:
        return bool(self._b[self._pair(effect)] & 0x80)

    def set_direction(self, reverse: bool, effect: int | None = None) -> None:
        a = self._pair(effect)
        self._b[a] = (self._b[a] | 0x80) if reverse else (self._b[a] & 0x7F)

    def speed(self, effect: int | None = None) -> int:
        return self._b[self._pair(effect) + 1] >> 4

    def set_speed(self, v: int, effect: int | None = None) -> None:
        self._range("speed", v, 0, 4)
        a = self._pair(effect) + 1
        self._b[a] = (v << 4) | (self._b[a] & 0x0F)

    def color(self, effect: int | None = None) -> int:
        return self._b[self._pair(effect) + 1] & 0x0F

    def set_color(self, v: int, effect: int | None = None) -> None:
        self._range("color", v, 0, 7)
        a = self._pair(effect) + 1
        self._b[a] = (self._b[a] & 0xF0) | v

    @property
    def win_mac(self) -> str:
        return "mac" if self._b[OFF_WINMAC] == 1 else "win"

    @win_mac.setter
    def win_mac(self, v: str) -> None:
        if v not in ("win", "mac"):
            raise ConfigError("win_mac must be 'win' or 'mac'")
        self._b[OFF_WINMAC] = 1 if v == "mac" else 0

    @property
    def sleep(self) -> int:
        return self._b[OFF_SLEEP]

    @sleep.setter
    def sleep(self, v: int) -> None:
        self._range("sleep", v, 0, 255)
        self._b[OFF_SLEEP] = v

    @property
    def debounce(self) -> int:
        return self._b[OFF_DEBOUNCE]

    @debounce.setter
    def debounce(self, v: int) -> None:
        self._range("debounce", v, 0, 4)
        self._b[OFF_DEBOUNCE] = v

    @property
    def link(self) -> str:
        return "radio" if self._b[OFF_LINK] == 1 else "wired"
