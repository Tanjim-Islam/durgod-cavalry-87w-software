import { afterEach, describe, expect, test, vi } from "vitest";
import { call, hasApi, isDesktop, onEvent, waitForBridge } from "./api";

afterEach(() => { delete window.pywebview; vi.restoreAllMocks(); });

describe("bridge", () => {
  test("hasApi is false for an empty api object", () => {
    window.pywebview = { api: {} };
    expect(hasApi()).toBe(false);
    expect(isDesktop()).toBe(false);
  });

  test("an empty api is not used until it is populated and pywebviewready fires", async () => {
    window.pywebview = { api: {} };
    const ready = waitForBridge();
    const get_state = vi.fn(async () => ({ connected: true, real: true }));
    window.pywebview.api.get_state = get_state;
    window.dispatchEvent(new Event("pywebviewready"));
    await ready;
    expect(isDesktop()).toBe(true);
    expect(await call<{ real: boolean }>("get_state")).toEqual({ connected: true, real: true });
    expect(get_state).toHaveBeenCalledOnce();
  });

  test("plain browser resolves immediately and uses the mock", async () => {
    await waitForBridge();
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
