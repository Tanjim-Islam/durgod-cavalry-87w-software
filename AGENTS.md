# AGENTS.md

Guidance for coding agents working in this repository.

## What this is

A Windows 11 tray app that replaces Durgod's software for the Durgod Cavalry 87W keyboard. Python engine and desktop shell in `engine/`, React UI in `ui/`. The keyboard protocol is documented in `PROTOCOL.md`; read it before touching anything in `engine/protocol.py`, `engine/links/` or `engine/codec/`.

## Layout

| Path | What it holds |
|---|---|
| `engine/protocol.py` | Command IDs, block sizes, allowed commands per link |
| `engine/links/` | `wired.py` (HID feature report 6), `radio.py` (2.4G dongle, report 0x13), `detect.py` |
| `engine/codec/` | Encode and decode each block: config, key layers, macros, key colors, palettes, snapshots |
| `engine/device.py` | `DeviceManager`: connect, mirror, backups, read-change-write-verify, replay after a dropped link; `Worker` thread |
| `engine/store.py` | `%APPDATA%\Cavalry87`: mirror, backups, profiles, settings |
| `engine/api.py` | `Api`: the only surface the UI uses; validates every input |
| `engine/shell/` | pywebview windows, `Bridge` (the JS surface), tray, flyout, autostart, custom title bar, macro recorder |
| `ui/src/` | React app; `bridge/mock.ts` is a full mock keyboard used outside the desktop app |
| `tests/` | pytest; `tests/fakes.py` has a fake keyboard for both links |
| `engine/version.py` | The app version, the single source for the package, the build and the update check |
| `engine/shell/updater.py` | Update check against GitHub releases (once at launch, or from Settings) and in-place install |
| `scripts/build.py`, `scripts/installer.iss` | Build the portable exe and the Setup installer (Inno Setup 6) into `dist/` |

## Commands

```bash
uv pip install -e ".[dev]"              # Python deps
pnpm -C ui install                      # UI deps
.venv/Scripts/python -m pytest          # Python tests (hardware tests excluded)
pnpm -C ui test                         # UI tests
pnpm -C ui exec tsc -b                  # type check
pnpm -C ui build                        # build the UI the app loads
.venv/Scripts/python -m engine          # run the app (--dev uses the Vite server on :5173, --tray starts hidden)
.venv/Scripts/python scripts/build.py   # portable exe + Setup installer into dist/ (needs Inno Setup 6)
```

Use `pnpm` for UI scripts. Use `npx` for one-off CLIs, since `pnpm dlx` and `pnpm create` don't work in this environment. The Python venv is managed by uv and has no pip.

## Rules

**The keyboard**
- Tests never touch the real keyboard. Hardware checks live in `tests/hardware/` behind `-m hardware` and are read-only.
- Every write goes through `Api` and `DeviceManager.apply`: backup first, read, change, write, verify. Don't write blocks from anywhere else.
- Never send commands outside `protocol.py`'s allowed sets. Never write more than 483 bytes of palette (identity data follows it).
- Never offer factory reset (system 0x04) or clearing Bluetooth (0x10) as remap targets, and never allow remapping Fn (slot 59) on layers 0 and 3. The API enforces this; keep it that way.
- Over 2.4G before the first cable read, only the config block can be read and written.

**Code**
- Keep comments short and high level. No comment spam.
- Prefer existing libraries over custom code.
- No new shadcn components: our `accent` and `muted` tokens clash with shadcn's meaning of those names. Reuse `Card`, `Segmented`, `Dialog`, `Switch`, `LevelSlider`.
- Two fonts only: Space Grotesk (display) and Inter (text). Colors come from the tokens in `ui/src/styles.css`, for both dark and light themes.
- Every page shows the keyboard picture (`PageShell`'s `keyboard` slot). Every control needs an accessible name; dialogs need a title and description.
- No em dashes in user-facing text.

**Commits and releases**
- Plain conventional commit messages.
- No AI attribution anywhere: no `Co-Authored-By` trailers, no "generated with" lines, no author headers or credits in files, commits, PRs or release notes.
- Release notes: a `# Cavalry 87W vX.Y.Z` heading, a one-line summary, then bullets starting with a past-tense verb (Added, Made, Fixed). Only the changes: no test results, no version bump notes.
