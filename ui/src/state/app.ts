import { create } from "zustand";
import { toast } from "sonner";
import * as bridge from "@/bridge/api";
import type { AppSettings, BackupInfo, KbState, ShortcutRow } from "@/bridge/types";

interface AppStore {
  state: KbState | null; shortcuts: ShortcutRow[] | null; profiles: string[]; backups: BackupInfo[];
  settings: AppSettings; busy: boolean;
  refresh(): Promise<void>;
  act(method: string, ...args: unknown[]): Promise<boolean>;
  loadShortcuts(): Promise<void>; loadProfiles(): Promise<void>; loadBackups(): Promise<void>;
  loadSettings(): Promise<void>; setAppSettings(p: Partial<AppSettings>): Promise<void>;
}

const err = (e: unknown) => toast.error(e instanceof Error ? e.message : String(e));

export const useApp = create<AppStore>((set, get) => ({
  state: null, shortcuts: null, profiles: [], backups: [], settings: { theme: "dark", autostart: false },
  busy: false,
  async refresh() {
    try { set({ state: await bridge.call<KbState>("get_state") }); } catch (e) { err(e); }
  },
  async act(method, ...args) {
    set({ busy: true });
    try {
      handleResult(await bridge.call<unknown>(method, ...args));
      return true;
    } catch (e) { err(e); return false; } finally { set({ busy: false }); }
  },
  async loadShortcuts() { try { set({ shortcuts: await bridge.call("get_shortcuts") }); } catch (e) { err(e); } },
  async loadProfiles() { try { set({ profiles: await bridge.call("list_profiles") }); } catch (e) { err(e); } },
  async loadBackups() { try { set({ backups: await bridge.call("list_backups") }); } catch (e) { err(e); } },
  async loadSettings() {
    try { set({ settings: await bridge.call<AppSettings>("get_app_settings") }); applyTheme(get().settings.theme); }
    catch (e) { err(e); }
  },
  async setAppSettings(p) {
    try {
      const s = await bridge.call<AppSettings>("set_app_settings", p.theme ?? null, p.autostart ?? null);
      set({ settings: s }); applyTheme(s.theme);
    } catch (e) { err(e); }
  },
}));

export function handleResult(r: unknown) {
  if (!r || typeof r !== "object" || Array.isArray(r)) return;
  const o = r as KbState;
  if (o.warning) toast(o.warning);
  if ("connected" in o) useApp.setState({ state: o });
}

export function applyTheme(theme: AppSettings["theme"]) {
  const dark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

let wired = false;
export function connectEvents() {
  if (wired) return;
  wired = true;
  bridge.onEvent((e) => {
    if (e.name === "error") toast.error(String(e.payload.message ?? "Keyboard error"));
    else if (e.name === "mirror_mismatch")
      toast("Keyboard settings changed while the app was away; the app now shows what's on the keyboard.");
    if (e.name === "state" || e.name === "link" || e.name === "mirror_mismatch") void useApp.getState().refresh();
  });
}
