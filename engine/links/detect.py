"""Which link is up right now, and how to open it."""
from __future__ import annotations

import hid

from .base import Link, LinkError
from .radio import HidPacketDevice, RadioLink
from .wired import WinFeatureDevice, WiredLink, find_wired_path
from ..protocol import RADIO_PID, RADIO_VID


def detect_link_kind() -> str | None:
    if find_wired_path():
        return "wired"
    if any(d["usage_page"] == 0xFF02 for d in hid.enumerate(RADIO_VID, RADIO_PID)):
        return "radio"
    return None


def open_link(kind: str) -> Link:
    if kind == "wired":
        path = find_wired_path()
        if not path:
            raise LinkError("keyboard cable link vanished")
        return WiredLink(WinFeatureDevice(path))
    if kind == "radio":
        link = RadioLink(HidPacketDevice())
        if not link.online():
            link.close()
            raise LinkError("dongle present but keyboard not connected")
        return link
    raise LinkError(f"unknown link kind {kind!r}")
