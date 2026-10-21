import type { KbState } from "@/bridge/types";

// What the app can do right now. Everything except "ready" and "partial" blocks the keyboard pages.
export type Blocked =
  | { kind: "starting" | "none" | "connecting" | "asleep" }
  | { kind: "wrong_model" | "connect_failed" | "lost"; detail: string };
export type DeviceStatus = { kind: "ready" | "partial" } | Blocked;

export function deviceStatus(s: KbState | null): DeviceStatus {
  if (!s) return { kind: "starting" };
  if (s.connected) return { kind: s.partial ? "partial" : "ready" };
  if (s.problem) return { kind: s.problem.code, detail: s.problem.message };
  if (s.searching) return { kind: "starting" };
  if (!s.link) return { kind: "none" };
  if (s.asleep) return { kind: "asleep" };
  return { kind: "connecting" };
}

export const blocked = (st: DeviceStatus): st is Blocked => st.kind !== "ready" && st.kind !== "partial";
