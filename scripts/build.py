"""Builds the Windows app into dist/: a portable single exe and a Setup installer.

Run: .venv/Scripts/python scripts/build.py   (the installer needs Inno Setup 6)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "Cavalry87"
ICON = ROOT / "engine" / "shell" / "icon.ico"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]

VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v}), prodvers=({v})),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', 'Cavalry 87W'),
    StringStruct('ProductName', 'Cavalry 87W'),
    StringStruct('FileVersion', '{s}'),
    StringStruct('ProductVersion', '{s}'),
    StringStruct('OriginalFilename', '{n}.exe')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
"""


def iscc() -> Path:
    """Inno Setup's compiler: INNO_ISCC, or the usual per-user and machine-wide install folders."""
    candidates = [os.environ.get("INNO_ISCC", ""),
                  Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
                  Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
                  Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe"]
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c)
    raise SystemExit("Inno Setup 6 not found: install it (winget install JRSoftware.InnoSetup) or set INNO_ISCC")


def run(*cmd: str) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True, shell=cmd[0] == "pnpm")


def pyinstaller(onefile: bool, work: Path, version_file: Path) -> None:
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--onefile" if onefile else "--onedir", "--name", NAME, "--icon", str(ICON),
        "--version-file", str(version_file), "--workpath", str(work / ("one" if onefile else "dir")),
        "--specpath", str(work), "--distpath", str(work / "out" / ("one" if onefile else "dir")),
        "--add-data", f"{ROOT / 'ui' / 'dist'};ui/dist", "--add-data", f"{ICON};engine/shell",
        "--paths", str(ROOT), str(ROOT / "scripts" / "cavalry87.py"))


def main() -> None:
    run("pnpm", "-C", "ui", "build")
    work, dist = ROOT / "build" / "pyinstaller", ROOT / "dist"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    dist.mkdir(exist_ok=True)
    nums = ", ".join((VERSION.split(".") + ["0", "0", "0"])[:4])
    version_file = work / "version.txt"
    version_file.write_text(VERSION_INFO.format(v=nums, s=VERSION, n=NAME), encoding="utf-8")

    pyinstaller(True, work, version_file)
    portable = dist / f"{NAME}-v{VERSION}-portable.exe"
    shutil.copy2(work / "out" / "one" / f"{NAME}.exe", portable)

    pyinstaller(False, work, version_file)
    run(str(iscc()), "/Q", f"/DAppVersion={VERSION}", f"/DSourceDir={work / 'out' / 'dir' / NAME}",
        f"/DOutputDir={dist}", f"/DIconFile={ICON}", str(ROOT / "scripts" / "installer.iss"))
    print("built", portable, dist / f"{NAME}-Setup-v{VERSION}.exe", sep="\n  ")


if __name__ == "__main__":
    main()
