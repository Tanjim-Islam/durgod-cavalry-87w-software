import type { DeviceEvent } from "./types";
import { createMock } from "./mock";

type Remote = Record<string, (...a: unknown[]) => Promise<unknown>>;
declare global {
  interface Window { pywebview?: { api: Remote }; __cavalryEmit?: (e: DeviceEvent) => void }
}

const listeners = new Set<(e: DeviceEvent) => void>();
window.__cavalryEmit = (e) => listeners.forEach((l) => {
  try { l(e); } catch (err) { console.error(err); }
});

let mock: Remote | null = null;
export const hasApi = () => {
  const api = window.pywebview?.api;
  return Boolean(api) && Object.values(api!).some((v) => typeof v === "function");
};
export const isDesktop = hasApi;

function remote(): Remote {
  if (hasApi()) return window.pywebview!.api;
  mock ??= createMock((e) => window.__cavalryEmit?.(e)) as unknown as Remote;
  return mock;
}

export async function call<T>(method: string, ...args: unknown[]): Promise<T> {
  const fn = remote()[method];
  if (!fn) throw new Error(`Unknown action: ${method}`);
  try {
    return (await fn(...args)) as T;
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : typeof e === "object" && e && "message" in e
      ? String((e as { message: unknown }).message) : String(e);
    throw new Error(msg.replace(/^ApiError:\s*/, ""));
  }
}

export function onEvent(cb: (e: DeviceEvent) => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export const windowAction = (name: "show_main" | "hide_flyout" | "minimize" | "quit") =>
  call<void>(name);

export function waitForBridge(): Promise<void> {
  if (hasApi()) return Promise.resolve();
  if (!window.pywebview && !navigator.userAgent.includes("Edg")) return Promise.resolve();
  return new Promise((res) => {
    window.addEventListener("pywebviewready", () => res(), { once: true });
    setTimeout(res, 1500);
  });
}
