export type Action =
  | { type: "none" } | { type: "fn" }
  | { type: "key"; hid: number; mods: number; high: boolean }
  | { type: "mouse"; code: number; b2: number; b3: number }
  | { type: "consumer"; usage: number }
  | { type: "macro"; index: number; mode: number; count: number }
  | { type: "system"; code: number }
  | { type: "lighting"; a: number; b: number }
  | { type: "raw"; data: string };

export type RGB = [number, number, number];

export interface Lighting {
  effect: number; brightness: number | null; speed: number | null; color: number | null;
  direction: boolean | null; keep_lights_on: boolean;
}
export interface KbSettings { win_mac: "win" | "mac"; sleep: number; debounce: number }
export interface MacroEvent { kind: string; code: number; release: boolean; delay_ms: number }
export interface Macro { name: string; events: MacroEvent[] }

export interface KbState {
  connected: boolean; link: "wired" | "radio" | null; partial: boolean; asleep: boolean;
  effects: { id: number; name: string }[]; key_names: Record<string, string>;
  lighting?: Lighting | null; settings?: KbSettings | null; layers?: Action[][] | null;
  macros?: Macro[] | null; key_colors?: RGB[] | null; palette?: RGB[][] | null;
  lighting_error?: string; settings_error?: string; layers_error?: string; macros_error?: string;
  key_colors_error?: string; palette_error?: string; warning?: string;
  problem?: Problem | null; notices?: Notice[]; pending?: boolean; searching?: boolean;
}
export interface Problem { code: "wrong_model" | "connect_failed" | "lost"; message: string }
export interface Notice { code: string; message: string }
export interface ShortcutRow {
  keys: string; group: string; label: string; slot: number | null; current: string;
  current_action: Action | null; changed: boolean;
}
export interface BackupInfo { name: string; created: string; factory: boolean; label: string }
export interface AppSettings { theme: "dark" | "light" | "system"; autostart: boolean }
export interface DeviceEvent { name: "state" | "link" | "mirror_mismatch" | "error" | "recording_stopped" | "window" | "update"; payload: Record<string, unknown> }
