import type { Macro, MacroEvent } from "@/bridge/types";
import { MOD_HID, hidName } from "./hid";

export const MACRO_LIMIT = 4096;
export const NAME_MAX = 30;
export const DELAY_MAX = 0xfffff;
// Engine layout: 4-byte table entry, then 1 + UTF-16 name + 4 bytes per event.
export const macroBytes = (ms: Macro[]) => ms.reduce((n, m) => n + 4 + 1 + 2 * m.name.length + 4 * m.events.length, 0);
export const MOUSE_BUTTONS: [number, string][] = [[1, "Left click"], [2, "Right click"], [4, "Middle click"], [8, "Back"], [16, "Forward"]];
const MOUSE_BTN: Record<number, string> = Object.fromEntries(MOUSE_BUTTONS);
const signed = (c: number) => (c > 127 ? c - 256 : c);

export function eventLabel(e: MacroEvent): string {
  const dir = e.release ? "up" : "down";
  switch (e.kind) {
    case "key": return `${hidName(e.code)} ${dir}`;
    case "modifier": return `${MOD_HID[e.code] ?? hidName(e.code)} ${dir}`;
    case "mouse_button": return `${MOUSE_BTN[e.code] ?? `Mouse ${e.code}`} ${dir}`;
    case "wheel": return `Wheel ${signed(e.code)}`;
    case "mouse_x": return `Move X ${signed(e.code)}`;
    case "mouse_y": return `Move Y ${signed(e.code)}`;
    default: return `${e.kind} ${e.code}`;
  }
}
export const tap = (hid: number, delay = 16): MacroEvent[] =>
  [{ kind: "key", code: hid, release: false, delay_ms: delay }, { kind: "key", code: hid, release: true, delay_ms: delay }];
export const click = (button: number, delay = 16): MacroEvent[] =>
  [{ kind: "mouse_button", code: button, release: false, delay_ms: delay }, { kind: "mouse_button", code: button, release: true, delay_ms: delay }];
export const totalMs = (m: Macro) => m.events.reduce((n, e) => n + e.delay_ms, 0);
