"""Update check against the GitHub releases: once at launch, and when asked from Settings.

An installed copy downloads the new Setup, checks its SHA-256 against the one GitHub publishes, and runs it;
the installer quits this app cleanly, updates it and opens it again. A portable copy just links to the release.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

log = logging.getLogger("cavalry")

REPO = "Tanjim-Islam/durgod-cavalry-87w-software"
LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
SETUP_ASSET = re.compile(r"^Cavalry87-Setup-v[\d.]+\.exe$")
TIMEOUT_S = 15
BUSY = {"checking", "downloading", "installing"}


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", v)[:3])


def is_installed() -> bool:
    """Frozen and installed by Setup (its uninstaller sits next to the exe), not the portable exe or a dev run."""
    exe = Path(sys.executable)
    return bool(getattr(sys, "frozen", False)) and any(exe.parent.glob("unins*.exe"))


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Cavalry87"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.load(r)


def _download(url: str, dest: Path, on_progress) -> str:
    """Saves url to dest; returns the file's SHA-256."""
    h = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": "Cavalry87"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r, open(dest, "wb") as f:
        total, done = int(r.headers.get("Content-Length") or 0), 0
        while chunk := r.read(256 * 1024):
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if total:
                on_progress(done / total)
    return h.hexdigest()


def _launch(setup: Path) -> None:
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(setup), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH=1"],
                     creationflags=flags, close_fds=True)


class Updater:
    def __init__(self, current: str, push, installed: bool | None = None, fetch=_fetch_json,
                 download=_download, launch=_launch, open_url=os.startfile, spawn=None):
        self.current, self._push = current, push
        self._fetch, self._download, self._launch, self._open = fetch, download, launch, open_url
        self._spawn = spawn or (lambda fn: threading.Thread(target=fn, name="cavalry-update", daemon=True).start())
        self._lock = threading.Lock()
        self._asset: dict | None = None
        self.state = {"status": "idle", "current": current, "latest": None, "url": None, "progress": 0.0,
                      "error": None, "installable": is_installed() if installed is None else installed}

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self.state)

    def _set(self, **changes) -> None:
        with self._lock:
            self.state.update(changes)
            state = dict(self.state)
        self._push("update", state)

    def check(self) -> dict:
        """Start a check unless one (or a download) is already running; returns the state right away."""
        with self._lock:
            if self.state["status"] in BUSY:
                return dict(self.state)
            self.state.update(status="checking", error=None)
        self._push("update", self.snapshot())
        self._spawn(self._check)
        return self.snapshot()

    def _check(self) -> None:
        try:
            rel = self._fetch(LATEST)
            latest = str(rel["tag_name"]).lstrip("v")
            self._asset = next((a for a in rel.get("assets", []) if SETUP_ASSET.match(a.get("name", ""))), None)
            newer = parse_version(latest) > parse_version(self.current)
            self._set(status="available" if newer else "current", latest=latest, url=rel.get("html_url"))
        except Exception as e:
            log.warning("update check failed: %s", e)
            self._set(status="error", error="Couldn't check for updates. Check your internet connection.")

    def install(self) -> dict:
        """Installed copy: download, verify and run the new Setup. Portable or no installer asset: open the page."""
        state = self.snapshot()
        if state["status"] != "available":
            return state
        if not state["installable"] or not self._asset:
            if state["url"]:
                self._open(state["url"])
            return state
        self._set(status="downloading", progress=0.0, error=None)
        self._spawn(self._install)
        return self.snapshot()

    def _install(self) -> None:
        asset = self._asset
        try:
            folder = Path(tempfile.gettempdir()) / "Cavalry87-update"
            folder.mkdir(exist_ok=True)
            dest = folder / asset["name"]
            last = [0.0]

            def progress(p: float) -> None:
                if p - last[0] >= 0.02 or p >= 1:
                    last[0] = p
                    self._set(progress=round(p, 3))
            digest = self._download(asset["browser_download_url"], dest, progress)
            expected = str(asset.get("digest") or "").removeprefix("sha256:")
            if expected and digest != expected:
                dest.unlink(missing_ok=True)
                raise ValueError("the download didn't match the published checksum")
            self._set(status="installing", progress=1.0)
            self._launch(dest)
        except Exception as e:
            log.warning("update install failed: %s", e)
            self._set(status="available", error=f"Couldn't install the update: {e}")
