import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => cleanup());
window.matchMedia ??= ((q: string) => ({ matches: false, media: q, onchange: null,
  addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
  dispatchEvent: () => false })) as typeof window.matchMedia;
globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

// Each test starts with a fresh bridge mock, a fresh store and no desktop bridge. Imported lazily so a
// test file's own vi.mock of these modules still applies.
let initial: unknown;
beforeEach(async () => {
  delete window.pywebview; delete window.chrome;
  try { (await import("@/bridge/api")).resetMock(); } catch { /* the test replaced the bridge module */ }
  const { useApp } = await import("@/state/app");
  initial ??= useApp.getState();
  useApp.setState(initial as ReturnType<typeof useApp.getState>, true);
});
