import type { Action } from "@/bridge/types";

export interface HidKey { hid: number; name: string; group: string }
const k = (group: string, list: [number, string][]) => list.map(([hid, name]) => ({ hid, name, group }));
const letters = Array.from({ length: 26 }, (_, i) => [0x04 + i, String.fromCharCode(65 + i)] as [number, string]);
const digits = Array.from({ length: 9 }, (_, i) => [0x1e + i, String(i + 1)] as [number, string]);
const fkeys = Array.from({ length: 12 }, (_, i) => [0x3a + i, `F${i + 1}`] as [number, string]);
const fhigh = Array.from({ length: 12 }, (_, i) => [0x68 + i, `F${i + 13}`] as [number, string]);

export const HID_KEYS: HidKey[] = [
  ...k("Letters", letters),
  ...k("Numbers", [...digits, [0x27, "0"]]),
  ...k("Function", [...fkeys, ...fhigh]),
  ...k("Editing", [[0x28, "Enter"], [0x29, "Esc"], [0x2a, "Backspace"], [0x2b, "Tab"], [0x2c, "Space"],
    [0x39, "Caps Lock"], [0x46, "Print Screen"], [0x47, "Scroll Lock"], [0x48, "Pause"], [0x65, "Menu"]]),
  ...k("Navigation", [[0x49, "Insert"], [0x4a, "Home"], [0x4b, "Page Up"], [0x4c, "Delete"], [0x4d, "End"],
    [0x4e, "Page Down"], [0x4f, "Right"], [0x50, "Left"], [0x51, "Down"], [0x52, "Up"]]),
  ...k("Symbols", [[0x2d, "-"], [0x2e, "="], [0x2f, "["], [0x30, "]"], [0x31, "\\"], [0x33, ";"], [0x34, "'"],
    [0x35, "`"], [0x36, ","], [0x37, "."], [0x38, "/"], [0x64, "ISO \\"], [0x87, "Intl \\"]]),
  ...k("Numpad", [[0x53, "Num Lock"], [0x54, "Num /"], [0x55, "Num *"], [0x56, "Num -"], [0x57, "Num +"],
    [0x58, "Num Enter"], ...Array.from({ length: 9 }, (_, i) => [0x59 + i, `Num ${i + 1}`] as [number, string]),
    [0x62, "Num 0"], [0x63, "Num ."]]),
];
const NAME = new Map(HID_KEYS.map((x) => [x.hid, x.name]));
export const hidName = (hid: number) => NAME.get(hid) ?? `Key 0x${hid.toString(16).padStart(2, "0")}`;

export const MODIFIERS = [{ bit: 0x01, name: "Left Ctrl" }, { bit: 0x02, name: "Left Shift" }, { bit: 0x04, name: "Left Alt" },
  { bit: 0x08, name: "Left Win" }, { bit: 0x10, name: "Right Ctrl" }, { bit: 0x20, name: "Right Shift" },
  { bit: 0x40, name: "Right Alt" }, { bit: 0x80, name: "Right Win" }];
export const MOD_HID: Record<number, string> = Object.fromEntries(MODIFIERS.map((m, i) => [0xe0 + i, m.name]));

export const CONSUMER: [number, string][] = [[0xe2, "Mute"], [0xe9, "Volume up"], [0xea, "Volume down"],
  [0xcd, "Play/Pause"], [0xb5, "Next track"], [0xb6, "Previous track"], [0xb7, "Stop"],
  [0x6f, "Screen brightness up"], [0x70, "Screen brightness down"], [0x18a, "Mail"], [0x192, "Calculator"],
  [0x194, "My Computer"], [0x221, "Search"], [0x223, "Browser home"], [0x224, "Browser back"],
  [0x225, "Browser forward"], [0x226, "Browser stop"], [0x227, "Browser refresh"], [0x22a, "Favorites"]];
export const SYSTEM_ALL: Record<number, string> = { 0x01: "Lock Win key", 0x04: "Factory reset", 0x05: "Bluetooth 1",
  0x06: "Bluetooth 2", 0x08: "2.4G mode", 0x09: "Wired mode", 0x0a: "Unknown (factory Fn+G)", 0x0b: "Backlight on/off",
  0x10: "Clear Bluetooth pairing", 0x15: "Windows mode", 0x16: "Mac mode" };
export const SYSTEM_OFFERED: [number, string][] = [0x01, 0x0b, 0x15, 0x16, 0x09, 0x08, 0x05, 0x06]
  .map((c) => [c, SYSTEM_ALL[c]]);
export const LIGHTING_FNS = [{ a: 0, b: 0, name: "Next effect" }, { a: 1, b: 0, name: "Change direction" },
  { a: 2, b: 0, name: "Next color" }, { a: 3, b: 1, name: "Brightness up" }, { a: 3, b: 2, name: "Brightness down" },
  { a: 4, b: 1, name: "Speed up" }, { a: 4, b: 2, name: "Speed down" }];
export const MOUSE: [number, string][] = [[1, "Left click"], [3, "Right click"], [2, "Middle click"],
  [4, "Back"], [5, "Forward"], [8, "Wheel up"], [9, "Wheel down"]];
const preset = (name: string, mods: number, hid: number) => ({ name, action: { type: "key", hid, mods, high: true } as Action });
export const PRESETS = [preset("Lock PC (Win+L)", 0x08, 0x0f), preset("Show desktop (Win+D)", 0x08, 0x07),
  preset("Run (Win+R)", 0x08, 0x15), preset("Close window (Alt+F4)", 0x04, 0x3d), preset("Undo (Ctrl+Z)", 0x01, 0x1d),
  preset("Save (Ctrl+S)", 0x01, 0x16), preset("Zoom in (Ctrl+=)", 0x01, 0x2e), preset("Zoom out (Ctrl+-)", 0x01, 0x2d),
  preset("Ctrl+Alt+Del", 0x05, 0x4c)];
export const NKRO_MAX = 0x70;

const key = (hid: number, mods = 0): Action => ({ type: "key", hid, mods, high: false });
// Factory base layer read from the real keyboard (slot -> action).
const BASE_HID: [number, number][] = [[0, 0x29], [1, 0x35], [2, 0x2b], [3, 0x39], [7, 0x1e], [8, 0x14], [9, 0x04],
  [10, 0x1d], [12, 0x3a], [13, 0x1f], [14, 0x1a], [15, 0x16], [16, 0x1b], [18, 0x3b], [19, 0x20], [20, 0x08],
  [21, 0x07], [22, 0x06], [24, 0x3c], [25, 0x21], [26, 0x15], [27, 0x09], [28, 0x19], [30, 0x3d], [31, 0x22],
  [32, 0x17], [33, 0x0a], [34, 0x05], [35, 0x2c], [36, 0x3e], [37, 0x23], [38, 0x1c], [39, 0x0b], [40, 0x11],
  [42, 0x3f], [43, 0x24], [44, 0x18], [45, 0x0d], [46, 0x10], [48, 0x40], [49, 0x25], [50, 0x0c], [51, 0x0e],
  [52, 0x36], [54, 0x41], [55, 0x26], [56, 0x12], [57, 0x0f], [58, 0x37], [60, 0x42], [61, 0x27], [62, 0x13],
  [63, 0x33], [64, 0x38], [65, 0x65], [66, 0x43], [67, 0x2d], [68, 0x2f], [69, 0x34], [70, 0x87], [72, 0x44],
  [73, 0x2e], [74, 0x30], [75, 0x31], [76, 0x64], [78, 0x45], [79, 0x2a], [80, 0x31], [81, 0x28], [84, 0x46],
  [85, 0x49], [86, 0x4c], [89, 0x50], [90, 0x47], [91, 0x4a], [92, 0x4d], [94, 0x52], [95, 0x51], [96, 0x48],
  [97, 0x4b], [98, 0x4e], [101, 0x4f]];
export const BASE_LAYER: Record<number, Action> = {
  ...Object.fromEntries(BASE_HID.map(([s, h]) => [s, key(h)])),
  4: key(0, 0x02), 5: key(0, 0x01), 11: key(0, 0x08), 17: key(0, 0x04), 53: key(0, 0x40), 82: key(0, 0x20),
  83: key(0, 0x10), 59: { type: "fn" },
};
const sys = (code: number): Action => ({ type: "system", code });
const cons = (usage: number): Action => ({ type: "consumer", usage });
const light = (a: number, b = 0): Action => ({ type: "lighting", a, b });
export const FN_LAYER: Record<number, Action> = { 11: sys(1), 12: cons(0xe2), 18: cons(0xea), 24: cons(0xe9),
  30: sys(0x0b), 33: sys(0x0a), 36: light(3, 1), 42: light(3, 2), 48: light(4, 2), 54: light(4, 1), 55: light(1),
  56: sys(0x15), 60: sys(1), 61: light(2), 62: sys(0x16), 66: cons(0x223), 72: cons(0x194), 78: light(0),
  84: sys(9), 85: sys(0x10), 86: sys(4), 90: sys(8), 96: sys(5), 97: sys(6) };
export const SWAP_LAYER: Record<number, Action> = { 9: key(0x50), 14: key(0x52), 15: key(0x51), 21: key(0x4f),
  89: key(0x04), 94: key(0x1a), 95: key(0x16), 101: key(0x07) };
