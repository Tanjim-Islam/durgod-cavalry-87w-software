import type { Action, AppSettings, BackupInfo, DeviceEvent, KbState, Macro, RGB, ShortcutRow } from "./types";

const EFFECTS = ["Always On", "Breathing", "Dream Rainbow", "Hair Trigger", "Walk in the Rain",
  "Rainbow Roulette", "Key Ripples", "The Stars", "Step on the Snow", "Continuous Flow",
  "Go with the Flow", "Like a Shadow", "Blinding Light Waves", "Spin the Windmill",
  "Colourful Waterfalls", "Flower Bloom", "Game Mode"];
const IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18];
const DEFAULT_GROUP: RGB[] = [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0], [255, 0, 255], [0, 255, 255], [255, 255, 255]];
const SHORTCUTS: [string, string, string][] = [
  ["Fn + F1", "Media", "Mute"], ["Fn + F2", "Media", "Volume down"], ["Fn + F3", "Media", "Volume up"],
  ["Fn + F10", "Media", "Browser home"], ["Fn + F11", "Media", "My Computer"],
  ["Fn + F4", "Lighting", "Backlight on/off"], ["Fn + F5", "Lighting", "Brightness up"],
  ["Fn + F6", "Lighting", "Brightness down"], ["Fn + F7", "Lighting", "Effect slower"],
  ["Fn + F8", "Lighting", "Effect faster"], ["Fn + F12", "Lighting", "Next effect"],
  ["Fn + 9", "Lighting", "Change direction"], ["Fn + 0", "Lighting", "Next color"],
  ["Fn + PrtSc", "Connection", "Wired mode"], ["Fn + ScrLk", "Connection", "2.4G mode (hold 3 s: re-pair dongle)"],
  ["Fn + Pause", "Connection", "Bluetooth 1 (hold: pairing)"], ["Fn + PgUp", "Connection", "Bluetooth 2 (hold: pairing)"],
  ["Fn + Ins", "Connection", "Clear Bluetooth pairing"], ["Fn + Pause + PgUp", "Connection", "Bluetooth broadcast (discoverable) mode"],
  ["Fn + F9", "System", "Lock Win key"], ["Fn + Win", "System", "Lock Win key"],
  ["Fn + O", "System", "Windows mode (not in manual)"], ["Fn + P", "System", "Mac mode (not in manual)"],
  ["Fn + Del", "System", "Factory reset"], ["Fn + G", "System", "Unknown factory function"],
];
const KEY_NAMES: Record<string, string> = { "0": "Esc", "45": "J", "59": "Fn", "96": "Pause" };

export function createMock(emit: (e: DeviceEvent) => void) {
  const wait = () => new Promise((r) => setTimeout(r, 150));
  const s: KbState = {
    connected: true, link: "radio", partial: false, asleep: false,
    effects: EFFECTS.map((name, i) => ({ id: IDS[i], name })), key_names: KEY_NAMES,
    lighting: { effect: 1, brightness: 4, speed: 3, color: 3, direction: false, keep_lights_on: true },
    settings: { win_mac: "win", sleep: 0, debounce: 0 },
    layers: Array.from({ length: 4 }, () => Array.from({ length: 126 }, (): Action => ({ type: "none" }))),
    macros: [] as Macro[], key_colors: Array.from({ length: 126 }, (): RGB => [0, 0, 0]),
    palette: Array.from({ length: 23 }, () => DEFAULT_GROUP.map((c) => [...c] as RGB)),
  };
  let profiles: string[] = ["Default"];
  const backups: BackupInfo[] = [
    { name: "factory", created: "2026-10-19T23:05:41", factory: true, label: "first connection" },
    { name: "20261020-101500-000000", created: "2026-10-20T10:15:00", factory: false, label: "before change" },
  ];
  let settings: AppSettings = { theme: "dark", autostart: false };
  const done = () => { emit({ name: "state", payload: {} }); return structuredClone(s); };
  const fail = (m: string) => { throw new Error(m); };

  return {
    async subscribe() {},
    async get_state() { await wait(); return structuredClone(s); },
    async set_lighting(effect?: number | null, brightness?: number | null, speed?: number | null,
                       color?: number | null, direction?: boolean | null) {
      await wait();
      const l = s.lighting!;
      if (effect != null) l.effect = effect;
      if (brightness != null) l.brightness = brightness;
      if (speed != null) l.speed = speed;
      if (color != null) l.color = color;
      if (direction != null) l.direction = direction;
      return done();
    },
    async set_settings(win_mac?: "win" | "mac" | null, sleep?: number | null, debounce?: number | null) {
      await wait();
      if (win_mac != null) s.settings!.win_mac = win_mac;
      if (sleep != null) { s.settings!.sleep = sleep; s.lighting!.keep_lights_on = sleep === 0; }
      if (debounce != null) s.settings!.debounce = debounce;
      return done();
    },
    async set_keep_lights_on(on: boolean) {
      await wait();
      s.lighting!.keep_lights_on = on; s.settings!.sleep = on ? 0 : 12;
      return done();
    },
    async get_shortcuts(): Promise<ShortcutRow[]> {
      await wait();
      return SHORTCUTS.map(([keys, group, label]) => ({ keys, group, label, slot: null, current: label,
                                                       current_action: null, changed: false }));
    },
    async list_profiles() { await wait(); return [...profiles]; },
    async save_profile(name: string) {
      await wait();
      if (!/^[\w .()-]{1,40}$/.test(name)) fail(`invalid name '${name}'`);
      profiles = [...new Set([...profiles, name])].sort();
      return [...profiles];
    },
    async apply_profile(name: string) { await wait(); if (!profiles.includes(name)) fail("No such profile"); return done(); },
    async delete_profile(name: string) { await wait(); profiles = profiles.filter((p) => p !== name); return [...profiles]; },
    async list_backups() { await wait(); return structuredClone(backups); },
    async restore_backup(name: string) { await wait(); if (!backups.some((b) => b.name === name)) fail("No such backup"); return done(); },
    async get_app_settings() { await wait(); return { ...settings }; },
    async set_app_settings(theme?: AppSettings["theme"] | null, autostart?: boolean | null) {
      await wait();
      settings = { theme: theme ?? settings.theme, autostart: autostart ?? settings.autostart };
      return { ...settings };
    },
    async export_profile_dialog(name: string) { await wait(); return `C:/Users/you/Documents/${name}.cavalry.json`; },
    async import_profile_dialog() { await wait(); return null; },
    async show_main() {}, async hide_flyout() {}, async minimize() {}, async quit() {},
  };
}
