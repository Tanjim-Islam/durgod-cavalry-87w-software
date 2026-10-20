"""Local files in %APPDATA%\\Cavalry87: mirror, backups, profiles, settings."""
from __future__ import annotations

import json
import os
import re
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from .codec.config import Config
from .codec.keymap import decode_layer
from .codec.macro import decode_macros
from .codec.snapshot import Snapshot, SnapshotError

NAME_RE = re.compile(r"[\w .()-]{1,40}")
BACKUP_RE = re.compile(r"factory|\d{8}-\d{6}-\d{6}")
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10))}


class StoreError(ValueError):
    pass


class StoreReadError(StoreError):
    """The file could not be read right now (I/O error); its content is unknown, not bad."""


class ProfileExists(StoreError):
    pass


class BackupInfo(BaseModel):
    name: str
    created: datetime
    factory: bool
    label: str = ""


class Settings(BaseModel):
    theme: Literal["dark", "light", "system"] = "dark"
    autostart: bool = False


def default_root() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "Cavalry87"


class Store:
    def __init__(self, root: Path, keep: int = 20):
        if keep < 1:
            raise StoreError("keep must be at least 1")
        self.root, self.keep = Path(root), keep
        for d in ("backups", "profiles"):
            (self.root / d).mkdir(parents=True, exist_ok=True)

    # -- helpers
    def _write(self, path: Path, data: dict) -> None:
        tmp = path.with_name(path.name + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, indent=1, default=str))
                f.flush()
                os.fsync(f.fileno())
            tmp.replace(path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    def _read(self, path: Path) -> dict:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            raise StoreReadError(f"cannot read {path.name}: {e}") from e
        except ValueError as e:  # not valid UTF-8
            raise StoreError(f"cannot read {path.name}: {e}") from e
        try:
            d = json.loads(text)
        except ValueError as e:
            raise StoreError(f"cannot read {path.name}: {e}") from e
        if not isinstance(d, dict):
            raise StoreError(f"{path.name} is not a JSON object")
        return d

    @staticmethod
    def _set_aside(p: Path) -> None:
        """Keep an unreadable file for inspection, out of the app's way."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        with suppress(OSError):
            p.replace(p.with_name(f"{p.stem}.corrupt-{stamp}.json"))

    @staticmethod
    def _snapshot(d: dict, where: str) -> Snapshot:
        try:
            return Snapshot.from_json(d["snapshot"])
        except KeyError as e:
            raise StoreError(f"{where}: missing {e}") from e
        except SnapshotError as e:
            raise StoreError(f"{where}: {e}") from e

    @staticmethod
    def _name(name: str) -> str:
        if (not isinstance(name, str) or not NAME_RE.fullmatch(name)
                or name != name.strip() or name.endswith(".")
                or name.split(".")[0].strip().upper() in RESERVED):
            raise StoreError(f"invalid name {name!r}")
        return name

    @staticmethod
    def _backup_name(name: str) -> str:
        if not isinstance(name, str) or not BACKUP_RE.fullmatch(name):
            raise StoreError(f"invalid backup name {name!r}")
        return name

    # -- mirror
    def load_mirror(self) -> Snapshot | None:
        p = self.root / "mirror.json"
        if not p.exists():
            return None
        try:
            return Snapshot.from_json(self._read(p))
        except SnapshotError as e:
            raise StoreError(f"mirror.json: {e}") from e

    def load_mirror_or_none(self) -> Snapshot | None:
        """The mirror, or None when missing or corrupt (a corrupt one is set aside).

        A transient read error raises StoreReadError and leaves the file alone.
        """
        try:
            return self.load_mirror()
        except StoreReadError:
            raise
        except StoreError:
            self._set_aside(self.root / "mirror.json")
            return None

    def save_mirror(self, s: Snapshot) -> None:
        s.validate()
        self._write(self.root / "mirror.json", s.to_json())

    # -- backups
    def save_backup(self, s: Snapshot, factory: bool = False, label: str = "") -> str:
        s.validate()
        if factory and self.has_factory():
            raise StoreError("factory snapshot already exists and is never overwritten")
        now = datetime.now()
        name = "factory"
        if not factory:
            while True:
                name = now.strftime("%Y%m%d-%H%M%S-%f")
                if not (self.root / "backups" / f"{name}.json").exists():
                    break
                now += timedelta(microseconds=1)
        self._write(self.root / "backups" / f"{name}.json",
                    {"created": now.isoformat(), "factory": factory, "label": str(label),
                     "snapshot": s.to_json()})
        if not factory:
            for old in [i for i in self.list_backups()
                        if not i.factory and i.name != "factory"][self.keep:]:
                with suppress(OSError):
                    (self.root / "backups" / f"{old.name}.json").unlink(missing_ok=True)
        return name

    def list_backups(self) -> list[BackupInfo]:
        out = []
        for p in (self.root / "backups").glob("*.json"):
            if not BACKUP_RE.fullmatch(p.stem):
                continue
            try:
                d = self._read(p)
                info = BackupInfo(name=p.stem, created=d["created"], factory=d["factory"],
                                  label=d.get("label", ""))
            except (StoreError, KeyError, ValidationError):
                continue
            out.append(info)
        return sorted(out, key=lambda i: i.created.replace(tzinfo=None), reverse=True)

    def load_backup(self, name: str) -> Snapshot:
        name = self._backup_name(name)
        return self._snapshot(self._read(self.root / "backups" / f"{name}.json"), name)

    def latest_backup(self) -> Snapshot | None:
        """Newest rolling (non-factory) backup, or None."""
        for i in self.list_backups():
            if not i.factory and i.name != "factory":
                try:
                    return self.load_backup(i.name)
                except StoreError:
                    return None
        return None

    def has_factory(self) -> bool:
        p = self.root / "backups" / "factory.json"
        if not p.exists():
            return False
        try:
            self._snapshot(self._read(p), "factory")
        except StoreReadError:
            return True  # present but unreadable right now: never capture a new one over it
        except StoreError:
            self._set_aside(p)
            return False
        return True

    # -- profiles
    def save_profile(self, name: str, s: Snapshot) -> None:
        name = self._name(name)
        s.validate()
        self._write(self.root / "profiles" / f"{name}.json", {"name": name, "snapshot": s.to_json()})

    def list_profiles(self) -> list[str]:
        return sorted(p.stem for p in (self.root / "profiles").glob("*.json"))

    def load_profile(self, name: str) -> Snapshot:
        name = self._name(name)
        return self._snapshot(self._read(self.root / "profiles" / f"{name}.json"), name)

    def delete_profile(self, name: str) -> None:
        (self.root / "profiles" / f"{self._name(name)}.json").unlink(missing_ok=True)

    def export_profile(self, name: str, path: Path) -> None:
        self._write(Path(path), self._read(self.root / "profiles" / f"{self._name(name)}.json"))

    def import_profile(self, path: Path, overwrite: bool = False) -> str:
        d = self._read(Path(path))
        name = self._name(d.get("name", Path(path).stem))
        s = self._snapshot(d, Path(path).name)
        try:
            Config(s.config)
            for layer in s.layers:
                decode_layer(layer)
            decode_macros(s.macros)
        except ValueError as e:
            raise StoreError(f"{Path(path).name}: {e}") from e
        if not overwrite and (self.root / "profiles" / f"{name}.json").exists():
            raise ProfileExists(f"a profile named {name!r} already exists")
        self.save_profile(name, s)
        return name

    # -- settings
    def load_settings(self) -> Settings:
        p = self.root / "settings.json"
        if not p.exists():
            return Settings()
        try:
            return Settings.model_validate(self._read(p))
        except ValidationError as e:
            raise StoreError(f"settings.json: {e}") from e

    def save_settings(self, s: Settings) -> None:
        self._write(self.root / "settings.json", s.model_dump())
