import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { READY_TIMEOUT_MS } from "@/bridge/api";
import { Boot } from "./Boot";

afterEach(() => { delete window.pywebview; delete window.chrome; vi.useRealTimers(); });

test("plain browser renders the app at once", () => {
  render(<Boot><p>app</p></Boot>);
  expect(screen.getByText("app")).toBeInTheDocument();
});

test("desktop webview shows Starting until the bridge is ready, an error after the timeout, and recovers", async () => {
  vi.useFakeTimers();
  window.chrome = { webview: {} };
  render(<Boot><p>app</p></Boot>);
  expect(screen.getByText("Starting…")).toBeInTheDocument();
  expect(screen.queryByText("app")).toBeNull();
  await act(async () => { await vi.advanceTimersByTimeAsync(READY_TIMEOUT_MS); });
  expect(screen.getByRole("alert")).toHaveTextContent(/didn't start/);
  expect(screen.queryByText("app")).toBeNull();
  window.pywebview = { api: { get_state: async () => ({}) } };
  act(() => { window.dispatchEvent(new Event("pywebviewready")); });
  expect(screen.getByText("app")).toBeInTheDocument();
});
