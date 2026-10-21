import { create } from "zustand";
import { toast } from "sonner";
import * as bridge from "@/bridge/api";

export interface UpdateState {
  status: "idle" | "checking" | "current" | "available" | "downloading" | "installing" | "error";
  current: string; latest: string | null; url: string | null; progress: number; error: string | null;
  installable: boolean;
}

interface UpdateStore {
  update: UpdateState | null;
  load(): Promise<void>; check(): Promise<void>; install(): Promise<void>;
}

const call = async (method: string) => {
  try { return await bridge.call<UpdateState | null>(method); }
  catch (e) { toast.error(e instanceof Error ? e.message : String(e)); return null; }
};

// The engine checks once at launch and pushes every change as an "update" event.
export const useUpdate = create<UpdateStore>((set) => ({
  update: null,
  async load() {
    try { set({ update: await bridge.call<UpdateState | null>("get_update") }); } catch { /* older engine or no bridge */ }
  },
  async check() { const u = await call("check_update"); if (u) set({ update: u }); },
  async install() { const u = await call("install_update"); if (u) set({ update: u }); },
}));

let wired = false;
export function connectUpdates() {
  if (wired) return;
  wired = true;
  bridge.onEvent((e) => { if (e.name === "update") useUpdate.setState({ update: e.payload as unknown as UpdateState }); });
}
