import type { DeviceEvent } from "./types";
import { createMock } from "./mock";

type Remote = Record<string, (...a: unknown[]) => Promise<unknown>>;
declare global {
  interface Window {
    pywebview?: { api: Remote }; chrome?: { webview?: unknown }; __cavalryEmit?: (e: DeviceEvent) => void;
  }
}

export const READY_TIMEOUT_MS = 10_000;

const listeners = new Set<(e: DeviceEvent) => void>();
window.__cavalryEmit = (e) => listeners.forEach((l) => {
  try { l(e); } catch (err) { console.error(err); }
});

let mock: Remote | null = null;
let ready: Promise<void> | null = null;

/** Test-only: forget the shared mock and any pending bridge wait. */
export function resetMock() { mock = null; ready = null; }

export const hasApi = () => {
  const api = window.pywebview?.api;
  return Boolean(api) && Object.values(api!).some((v) => typeof v === "function");
};
// pywebview injects its api after the page scripts run; WebView2's own object is there from the start.
export const inWebView = () => Boolean(window.chrome?.webview || window.pywebview);

async function remote(): Promise<Remote> {
  if (inWebView()) { await waitForBridge(); return window.pywebview!.api; }
  mock ??= createMock((e) => window.__cavalryEmit?.(e)) as unknown as Remote;
  return mock;
}

export async function call<T>(method: string, ...args: unknown[]): Promise<T> {
  // Once ready, invoke synchronously so window actions fire within the triggering event.
  const fn = (hasApi() ? window.pywebview!.api : await remote())[method];
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

/** Resolves at once in a plain browser (mock); in the desktop app, when the real api is in. */
export function waitForBridge(timeoutMs = READY_TIMEOUT_MS): Promise<void> {
  if (hasApi() || !inWebView()) return Promise.resolve();
  ready ??= new Promise<void>((res, rej) => {
    const finish = (ok: boolean) => {
      clearTimeout(timer);
      removeEventListener("pywebviewready", onReady);
      ready = null;
      if (ok) res(); else rej(new Error("The app's engine didn't start. Restart Cavalry."));
    };
    const onReady = () => { if (hasApi()) finish(true); };
    const timer = setTimeout(() => finish(false), timeoutMs);
    addEventListener("pywebviewready", onReady);
  });
  return ready;
}
