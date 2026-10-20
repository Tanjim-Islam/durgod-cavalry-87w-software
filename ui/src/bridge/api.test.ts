import { afterEach, describe, expect, test, vi } from "vitest";
import { call, hasApi, inWebView, onEvent, READY_TIMEOUT_MS, waitForBridge } from "./api";

afterEach(() => { delete window.pywebview; delete window.chrome; vi.useRealTimers(); vi.restoreAllMocks(); });

const settled = async (p: Promise<unknown>) => {
  let done = false;
  p.then(() => { done = true; }, () => { done = true; });
  await new Promise((r) => setTimeout(r, 20));
  return done;
};

describe("bridge", () => {
  test("hasApi is false for an empty api object, but that is still the desktop webview", () => {
    window.pywebview = { api: {} };
    expect(hasApi()).toBe(false);
    expect(inWebView()).toBe(true);
  });

  test("in WebView2 a call waits for pywebviewready and never reaches the mock", async () => {
    window.chrome = { webview: {} };
    const pending = call<{ real?: boolean }>("get_state");
    expect(await settled(pending)).toBe(false);
    const get_state = vi.fn(async () => ({ connected: true, real: true }));
    window.pywebview = { api: { get_state } };
    window.dispatchEvent(new Event("pywebviewready"));
    expect(await pending).toEqual({ connected: true, real: true });
    expect(get_state).toHaveBeenCalledOnce();
  });

  test("in WebView2 a bridge that never comes up fails the call instead of using fake data", async () => {
    vi.useFakeTimers();
    window.chrome = { webview: {} };
    const pending = call("get_state");
    const outcome = expect(pending).rejects.toThrow(/didn't start/);
    await vi.advanceTimersByTimeAsync(READY_TIMEOUT_MS);
    await outcome;
  });

  test("an empty api is not used until it is populated and pywebviewready fires", async () => {
    window.pywebview = { api: {} };
    const ready = waitForBridge();
    const get_state = vi.fn(async () => ({ connected: true, real: true }));
    window.pywebview.api.get_state = get_state;
    window.dispatchEvent(new Event("pywebviewready"));
    await ready;
    expect(await call<{ real: boolean }>("get_state")).toEqual({ connected: true, real: true });
    expect(get_state).toHaveBeenCalledOnce();
  });

  test("plain browser resolves immediately and uses the mock", async () => {
    expect(inWebView()).toBe(false);
    expect(await settled(waitForBridge())).toBe(true);
    const s = await call<{ connected: boolean }>("get_state");
    expect(s.connected).toBe(true);
  });

  test("ApiError prefix is stripped from a pywebview-style rejection", async () => {
    window.pywebview = { api: { boom: () => Promise.reject({ message: "ApiError: No such profile" }) } };
    await expect(call("boom")).rejects.toThrow(/^No such profile$/);
  });

  test("a throwing listener does not block the others", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const seen = vi.fn();
    const off1 = onEvent(() => { throw new Error("bad"); });
    const off2 = onEvent(seen);
    window.__cavalryEmit!({ name: "state", payload: {} });
    expect(seen).toHaveBeenCalledOnce();
    off1(); off2();
  });
});
