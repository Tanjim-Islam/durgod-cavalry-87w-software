import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi, type Mock } from "vitest";
import { createMock } from "@/bridge/mock";
import App from "./App";

test("sidebar navigates between pages with the connection pill shown", async () => {
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Lighting" })).toBeInTheDocument();
  expect(await screen.findByText("2.4G · connected")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Shortcuts" }));
  expect(await screen.findByRole("heading", { name: "Shortcuts" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Macros" }));
  expect(await screen.findByRole("heading", { name: "Macros" })).toBeInTheDocument();
});

test("state and settings are fetched again when pywebviewready arrives after mount", async () => {
  const base = createMock(() => {}) as unknown as Record<string, (...a: unknown[]) => Promise<unknown>>;
  const api: Record<string, Mock> = {};
  for (const k of Object.keys(base)) api[k] = vi.fn(base[k]);
  window.pywebview = { api: api as never };
  try {
    render(<App />);
    await waitFor(() => expect(api.get_state).toHaveBeenCalledTimes(1));
    expect(api.get_app_settings).toHaveBeenCalledTimes(1);
    window.dispatchEvent(new Event("pywebviewready"));
    await waitFor(() => expect(api.get_state).toHaveBeenCalledTimes(2));
    expect(api.get_app_settings).toHaveBeenCalledTimes(2);
  } finally { delete window.pywebview; }
});
