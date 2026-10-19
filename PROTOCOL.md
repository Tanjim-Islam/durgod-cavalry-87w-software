# Durgod Cavalry 87W protocol reference

Sources: live probing of the keyboard, plus a full Ghidra decompile of Durgod's official app (`Cavalry87w-DURGOD_Engine-Setup-v2.0.zip` from durgod.com: unpacked with innoextract, never run). The keyboard class in the app is `CDevG5KB` (wired) and `CDev3632` (2.4G).

## 1. Capability summary

| Feature | Wired | 2.4G | Status |
|---|---|---|---|
| Read all lighting settings (effect, brightness, speed, color, direction) | `0x84` | `0x44` | **Tested** |
| Change saved settings (any config byte) | `0x04` | `0x04` | **Tested** (Win/Mac, brightness, color; both links) |
| Win/Mac mode | cfg `0x1A` | same | **Tested** |
| Live per-key RGB (any color, any key, app-driven animations) | `0x08` | `0x88` | Wired **tested (seen)**. 2.4G accepted, not visually confirmed |
| Effect select (17 effects) / speed / direction / game mode | cfg bytes | same | Mapped from Fn tests, same write path |
| Sleep timeout (30 s units, 0 = never) | cfg `0x18` | same | **Tested** (write + read-back + restore, 2.4G) |
| Debounce | cfg `0x03` | same | **Tested** (write + read-back + restore, 2.4G) |
| Custom RGB palettes (effects use any color, not just 8 presets) | `0x0A`, read `0x8A` | `0x09` | **Tested both links** (marker, read-back over wired) |
| Saved per-key colors (persistent, Game Mode) | `0x06`, read `0x86` | `0x02` | **Tested both links** (read-back over wired) |
| Full key remap, 4 layers x 126 keys | `0x03` (sub = layer), read `0x83` | `0x01` (write only) | **Proven by real keypress** on both links (Fn+J sent F21 wired, F23 after a 2.4G write) |
| Hardware macros (stored on keyboard) | `0x05`, read `0x85` | `0x03` (sub = 512-byte block 0..7) | **Proven by real keypress on both links**: Fn-layer and base-layer macros, incl. modifier combos (2.4G: written over the dongle) |
| Music visualizer (app streams audio levels) | `0x0E` (+ paged `0x0C`) | `0x8E` | Decoded, not tested |
| Live "a setting changed" notification | input report 3 | n/a | **Tested** |
| Connection link detection | which USB device exists | cfg `0x0E` = 1 on 2.4G | **Tested** |
| Battery level / charging state | none | none | **Impossible**: firmware + official app don't support it |
| Switch wired/2.4G/BT, pairing, factory reset from PC | none found | none found | Fn keys only (could be put on a remapped key) |

## 2. Wired protocol (USB 258A:010C, interface 1, page 0xFF00)
- Col06 feature report 6, 520 bytes: `[06][cmd][sub][00][pkt_count][pkt_index][size_lo][size_hi][512 data bytes]`
  - Report ID is 6 because KB.ini `Fw=24` (0x18). Other Fw values use report 9.
  - Write: SetFeature. Read: SetFeature with `cmd|0x80`, then GetFeature.
  - Write ack on GetFeature: `04 04 04 04 04 04 5a a5`.
- Col03 input report 3: `03 08 00 01` whenever an Fn shortcut changes something.
- Commands (from the app):
  | cmd | Name in app | Data |
  |---|---|---|
  | `0x82` | GetPassword (identify) | 6 bytes `03 00 00 00 00 7B` (7B = model) |
  | `0x84` / `0x04` | GetLED / SetLED (config) | 128 bytes, map below |
  | `0x83` / `0x03` | Matrix (key layer), sub = layer 0..3 | 126 keys x 4 bytes = 504 |
  | `0x05` | SetMacro | macro buffer |
  | `0x06` | SetGame (saved per-key colors), sub = color group | 126 x 3 bytes, R/G/B planes |
  | `0x0A` | SetLedRgbTab (effect palettes) | (n+1) x 21 bytes (7 RGB colors per effect) |
  | `0x08` | Direct per-key RGB (RAM) | 0x17A bytes RGB, needs refresh ~1/s |
  | `0x0E` | Music/light bar data | |
  | `0x0C` | Paged bulk data (4 KB pages) | |
  | `0x0B` | SetScreenParam | for models with a screen, not this one |
  | `0x88` | GetRealData | raw firmware memory (what we saw as 8051 code) |
- Never send unknown commands. They return memory garbage, and the platform is known to brick on bad writes.

## 3. 2.4G protocol (dongle 3554:FA09, page 0xFF02, report 0x13)
- 20-byte packets: `[13][cmd][total][index][(sub<<4)|len][14 data bytes][sum of bytes 0..18]`
- Writes are split into 14-byte packets. Each packet is acked by an echo of the cmd.
- Reads: send `[13][cmd][01]...`. The reply is multi-packet (byte2 & 0x7F = total, byte3 = index, byte4 low nibble = length).
- Radio drops packets sometimes. Merge by index across retries (`probe/dongle.py` does this).
- Commands: `0x05` identify, `0x07` online status (1 = keyboard connected), `0x44` read config, `0x04` write config, `0x01` layer (sub = layer), `0x02` per-key colors, `0x03` macros, `0x09` palettes, `0x88` live RGB (no ack), `0x8E` music data.
- No layer/macro/color *reads* over 2.4G. The official app only reads config there.
- `0x88` live RGB: `[13][88][1][0][0x23][R][G][B]` = whole board; `(0x1<<4)|len` + `R,G,B,count,keys...` = per key (from OpenRGB #5166).

## 4. Config block (128 bytes, same over both links)
| Offset | Meaning |
|---|---|
| `0x03` | Debounce |
| `0x09` | Game Mode flag |
| `0x0A` | Current effect `0x01`..`0x12` (0x0E skipped). 1 = Always Light (static), 0x0B = default, 0x12 = Game Mode |
| `0x0B` | 0x20 base |
| `0x0E` | 1 when connected over 2.4G, 0 wired |
| `0x16` | Optional timer value (app writes 0 by default) |
| `0x17` | OS auto-detect toggle (on models that support it) |
| `0x18` | Sleep/backlight-off timeout. **0 = never: lights stay on (user-confirmed 2026-10-20, set over 2.4G).** The app assumes 30 s units, but the factory value `0x0C` turned lights off after ~1-2 min, so real units are likely ~10 s (unverified) |
| `0x1A` | Win/Mac: 00 Windows, 01 Mac (Fn+O / Fn+P) |
| `0x38`,`0x39` | `ff ff` |
| `0x38+2e` | Effect e: brightness 0..4, bit7 = direction |
| `0x39+2e` | Effect e: speed 0..4 (high nibble), color 0..7 (low nibble, 7 = random/multicolor) |
| `0x7E`,`0x7F` | `5a a5` signature |

## 5. Key entry format (layers, 4 bytes per key, LE uint32 = bytes as listed)
| Bytes | Meaning |
|---|---|
| `00 mods k1 k2` | Keyboard key + modifier mask (01 LCtrl, 02 LShift, 04 LAlt, 08 LWin, 10 RCtrl, 20 RShift, 40 RAlt, 80 RWin). Base layer puts the HID code in byte 3 (Esc = `00 00 00 29`). Shortcut presets put it in byte 2 (Ctrl+Z = `00 01 1d 00`) |
| `01 xx yy 00` | Mouse: left/right/middle/back/forward buttons, wheel up/down |
| `02 00 hi lo` | Consumer key, 16-bit usage big-endian (mute `02 00 00 e2`, browser `02 00 02 23`): mute E2, vol E9/EA, play/pause CD, next B5, prev B6, stop B7, mail 018A, calc 0192, My Computer 0194, browser 0221/0223-0227/022A, screen brightness 6F/70 |
| `03 mode count id-1` | Macro: mode 1 = play `count` times, 2 = repeat while held, 4 = toggle |
| `01 ...` | Built-in presets include Ctrl+Z/S, Alt+F4, Win+L, Win+R, Win+D, Ctrl+=/-, Ctrl+Alt+Del (encoded as key + modifiers) |
| `07 00 00 xx` | System: 01 Win lock, 04 factory reset, 05/06 BT1/BT2, 08 2.4G, 09 wired, 0A ?, 0B backlight off, 10 clear BT, 15 Windows mode, 16 Mac mode |
| `08 aa bb 00` | Lighting: 00 effect cycle, 01 direction, 02 color cycle, 03 01/02 brightness up/down, 04 01/02 speed up/down |
| `0d ...` | Fn-type key |
- Layers: 0 = base, 1 = Fn, 2 = empty, 3 = WASD <-> arrow swap (hidden). Slot index = column*6 + row (e.g. J = 45, Esc = 0).
- Macro buffer (cmd `0x05`, always 4096 bytes in 8 packets of 512, read `0x85` with pkt index): N x `[offset u16][size u16]` table, then blobs.
  - Blob: `[name byte length][name UTF-16LE]` then 4-byte events `[(type<<4)|delay>>16, bit7 = release][delay>>8][delay][code]`.
  - Types: **0 normal key** (HID), **1 modifier** (HID E0-E7), 2 mouse button (1 L, 2 R, 4 M, 8 back, 10 fwd), 3 mouse X, 4 mouse Y, 5 wheel. Delay up to 0xFFFFF ms.
  - Wired NKRO report only covers HID 0x04-0x70, so macro/remap keys must stay in that range in wired mode (F22-F24 won't send).
  - Working example: `0c 00 0b 00 ...` table, blob `02 54 00 | 00 00 10 68 | 80 00 10 68` = "T": F13 down, 16 ms, F13 up.

## 6. Palette storage
- Write `0x0A` stores the payload as-is from offset 0. Read `0x8A`. 21 bytes per group (7 RGB colors), group g = effect g. Default: red, green, blue, yellow, magenta, cyan, white.
- 23 groups = 483 bytes. **Bytes 483+ hold the identity data (`03 00 00 00 00 7b`): never write more than 483 bytes.**

## 6b. Battery (closed)
- 6-hour 2.4G drain test: the dongle's `64 64 64` bytes never changed.
- Official app: `ShowPower=0` for this model. Keyboard classes' GetPower is a stub that always fails, and wired battery is hardcoded to 100. Only the mouse class has a real GetPower.
- Result: no battery or charging info exists for any software. The red LED is the only indicator.

## Verification
Proven by a real keypress (Windows low-level hook saw the output):
- Key remap on both links: Fn+J sent F21 after a wired write and F23 after a 2.4G write.
- Hardware macros on both links, for Fn-layer and base-layer macros, including modifier combos (Fn+J -> F13, Pause -> F14, Fn+K -> Shift+F15). Macro keys must use event type 0 and stay in HID 0x04-0x70 on wired.

Proven by write plus read-back (and restore):
- Config bytes (Win/Mac, brightness, color, sleep timeout, debounce) on both links.
- Per-key colors and palettes on both links (read-back over wired).
- Layers, macros, per-key colors and palettes written over 2.4G were read back over wired and matched exactly; nothing else changed.

Seen or accepted only:
- Live per-key RGB: seen on wired; accepted but not visually confirmed on 2.4G.

Decoded, not tested: music visualizer (`0x0E`, `0x8E`).

Known hazard: a 2.4G to wired switch right after radio writes once failed USB enumeration (transient, data intact). Do not switch modes or write while the keyboard may still be saving to flash, and retry enumeration.

## Safety limits
- Block sizes are hard limits: config 128 (signature `5a a5` at 0x7E), layer 504, macros 4096, key colors 378, palette 483 (never more: bytes after it hold the identity data).
- Only whitelisted command IDs may be sent. Never firmware update, never `GetRealData` (`0x88` wired), never unknown commands.
- No write until the link has been stable 5 s. Backup before every write batch; factory snapshot before the first write ever.
- Wired NKRO only sends HID 0x04-0x70; anything higher must be flagged.
- Fn-shortcut changes are detected by polling the config block every poll (both links).
