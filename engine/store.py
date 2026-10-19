"""Local files in %APPDATA%\\Cavalry87: mirror, backups, profiles, settings."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from .codec.snapshot import Snapshot, SnapshotError

NAME_RE = re.compile(r"[\w .()-]{1,40}")
BACKUP_RE = re.compile(r"factory|\d{8}-\d{6}-\d{6}")
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10))}


class StoreError(ValueError):
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
            tmp.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
            tmp.replace(path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    def _read(self, path: Path) -> dict:
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise StoreError(f"cannot read {path.name}: {e}") from e
        if not isinstance(d, dict):
            raise StoreError(f"{path.name} is not a JSON object")
        return d

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

    def has_factory(self) -> bool:
        return (self.root / "backups" / "factory.json").exists()

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

    def import_profile(self, path: Path) -> str:
        d = self._read(Path(path))
        name = self._name(d.get("name", Path(path).stem))
        self.save_profile(name, self._snapshot(d, Path(path).name))
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
