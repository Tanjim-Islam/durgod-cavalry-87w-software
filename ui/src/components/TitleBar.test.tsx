import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { TitleBar } from "./TitleBar";

test("caption buttons call the window and the maximize icon follows the window state", async () => {
  const api = { minimize: vi.fn(async () => {}), toggle_maximize: vi.fn(async () => {}), hide_main: vi.fn(async () => {}) };
  window.pywebview = { api: api as never };
  render(<TitleBar />);
  await userEvent.click(screen.getByRole("button", { name: "Minimize" }));
  await userEvent.click(screen.getByRole("button", { name: "Maximize" }));
  await userEvent.click(screen.getByRole("button", { name: "Close to tray" }));
  expect(api.minimize).toHaveBeenCalled();
  expect(api.toggle_maximize).toHaveBeenCalled();
  expect(api.hide_main).toHaveBeenCalled();
  window.__cavalryEmit?.({ name: "window", payload: { maximized: true } });
  expect(await screen.findByRole("button", { name: "Restore" })).toBeInTheDocument();
  expect(document.querySelector("header")).toHaveClass("app-drag");
});
