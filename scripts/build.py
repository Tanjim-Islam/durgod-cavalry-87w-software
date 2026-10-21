"""Builds the Windows app into dist/: a portable single exe and a zipped folder build.

Run: .venv/Scripts/python scripts/build.py
"""
from __future__ import annotations

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
  ffi=FixedFileInfo(filevers=({v}, 0), prodvers=({v}, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', 'Cavalry 87W'),
    StringStruct('ProductName', 'Cavalry 87W'),
    StringStruct('FileVersion', '{s}'),
    StringStruct('ProductVersion', '{s}'),
    StringStruct('OriginalFilename', '{n}.exe')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
"""


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
    archive = shutil.make_archive(str(dist / f"{NAME}-v{VERSION}-win64"), "zip", work / "out" / "dir")
    print("built", portable, archive, sep="\n  ")


if __name__ == "__main__":
    main()
