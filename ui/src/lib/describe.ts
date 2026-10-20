import type { Action } from "@/bridge/types";
import { BASE_LAYER, CONSUMER, LIGHTING_FNS, MODIFIERS, MOUSE, SYSTEM_ALL, hidName } from "./hid";

const CONS = new Map(CONSUMER);
const MOUSE_NAME = new Map(MOUSE);

export function describe(a: Action): string {
  switch (a.type) {
    case "none": return "Nothing";
    case "fn": return "Fn";
    case "key": {
      const parts = MODIFIERS.filter((m) => a.mods & m.bit).map((m) => m.name);
      if (a.hid) parts.push(hidName(a.hid));
      return parts.join(" + ") || "Nothing";
    }
    case "consumer": return CONS.get(a.usage) ?? `Media 0x${a.usage.toString(16)}`;
    case "system": return SYSTEM_ALL[a.code] ?? `System 0x${a.code.toString(16)}`;
    case "lighting": return LIGHTING_FNS.find((f) => f.a === a.a && f.b === a.b)?.name ?? `Lighting ${a.a}/${a.b}`;
    case "macro": return `Macro ${a.index + 1}`;
    case "mouse": return MOUSE_NAME.get(a.code) ?? `Mouse ${a.code}`;
    case "raw": return `Raw ${a.data}`;
  }
}

export const naturalAction = (slot: number): Action => BASE_LAYER[slot] ?? { type: "none" };
const same = (a: Action, b: Action) => JSON.stringify(a) === JSON.stringify(b);
export const isRemapped = (layer: number, slot: number, a: Action) =>
  layer === 0 ? !same(a, naturalAction(slot)) : a.type !== "none";
