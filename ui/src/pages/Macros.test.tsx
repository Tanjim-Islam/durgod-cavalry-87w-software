import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi, type Mock } from "vitest";
import { createMock } from "@/bridge/mock";
import type { KbState } from "@/bridge/types";
import { useApp } from "@/state/app";
import { tap } from "@/lib/macro";
import { Macros } from "./Macros";

// Route the bridge through a spied copy of the mock engine.
function installApi(): Record<string, Mock> {
  const base = createMock((e) => window.__cavalryEmit?.(e)) as unknown as Record<string, (...a: unknown[]) => Promise<unknown>>;
  const api: Record<string, Mock> = {};
  for (const k of Object.keys(base)) api[k] = vi.fn(base[k]);
  window.pywebview = { api: api as never };
  return api;
}

test("record, name, save and assign a macro", async () => {
  await useApp.getState().refresh();
  render(<Macros />);
  await userEvent.click(await screen.findByRole("button", { name: "New macro" }));
  await userEvent.type(screen.getByRole("textbox", { name: "Macro name" }), "Hi");
  await userEvent.click(screen.getByRole("button", { name: "Record" }));
  await userEvent.click(await screen.findByRole("button", { name: "Stop recording" }));
  expect(await screen.findByText("H down")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(useApp.getState().state?.macros?.[0]?.name).toBe("Hi"));
  await userEvent.click(screen.getByRole("button", { name: "Assign to key" }));
  await userEvent.click(await screen.findByRole("radio", { name: "Fn layer" }));
  await userEvent.click(screen.getByRole("button", { name: "K" }));
  await userEvent.click(screen.getByRole("button", { name: "Assign" }));
  await waitFor(() => expect(useApp.getState().state?.layers?.[1][51]).toEqual({ type: "macro", index: 0, mode: 1, count: 1 }));
});

test("storage meter and delete confirm", async () => {
  const api = installApi();
  try {
    await api.save_macro(null, { name: "Seed", events: tap(0x04) });
    await api.remap_key(1, 51, { type: "macro", index: 0, mode: 1, count: 1 });
    await useApp.getState().refresh();
    render(<Macros />);
    const meter = await screen.findByRole("meter", { name: "Macro storage" });
    expect(meter).toHaveAttribute("aria-valuemax", "4096");
    expect(meter).toHaveAttribute("aria-valuenow", String(4 + 1 + 8 + 8));
    await userEvent.click(screen.getByRole("button", { name: "Macro 1: Seed" }));
    expect(screen.getByRole("spinbutton", { name: "Delay before event 1, A down" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Remove event 2, A up" }));
    expect(screen.getByText("This macro leaves A held down")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(await screen.findByText(/Keys that play this macro are unbound/)).toBeInTheDocument();
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(useApp.getState().state?.macros).toEqual([]));
    expect(useApp.getState().state?.layers?.[1][51]).toEqual({ type: "none" });
  } finally { delete window.pywebview; }
});

test("stop recording stays reachable when the macros can't be read", async () => {
  const api = installApi();
  try {
    await useApp.getState().refresh();
    render(<Macros />);
    await userEvent.click(await screen.findByRole("button", { name: "New macro" }));
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    await screen.findByRole("button", { name: "Stop recording" });
    const real = api.get_state.getMockImplementation()!;
    api.get_state.mockImplementation(async () => ({ ...((await real()) as KbState), macros: null, macros_error: "Macro memory is corrupt" }));
    await useApp.getState().refresh();
    expect(await screen.findByText("Macro memory is corrupt")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Stop recording" }));
    await waitFor(() => expect(api.record_macro_stop).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Stop recording" })).not.toBeInTheDocument());
  } finally { delete window.pywebview; }
});

test("recording stops when the open macro goes away", async () => {
  const api = installApi();
  try {
    await api.save_macro(null, { name: "Seed", events: tap(0x04) });
    await useApp.getState().refresh();
    render(<Macros />);
    await userEvent.click(await screen.findByRole("button", { name: "Macro 1: Seed" }));
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    await screen.findByRole("button", { name: "Stop recording" });
    await api.delete_macro(0);
    await useApp.getState().refresh();
    await waitFor(() => expect(api.record_macro_stop).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Stop recording" })).not.toBeInTheDocument());
  } finally { delete window.pywebview; }
});

test("leaving while the recorder is starting still stops it", async () => {
  const api = installApi();
  try {
    let release!: () => void;
    const real = api.record_macro_start.getMockImplementation()!;
    api.record_macro_start.mockImplementation(() => new Promise<void>((r) => { release = () => void real().then(() => r()); }));
    await useApp.getState().refresh();
    const { unmount } = render(<Macros />);
    await userEvent.click(await screen.findByRole("button", { name: "New macro" }));
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    expect(screen.getByRole("button", { name: "Record" })).toBeDisabled();
    unmount();
    expect(api.record_macro_stop).not.toHaveBeenCalled();
    release();
    await waitFor(() => expect(api.record_macro_stop).toHaveBeenCalledTimes(1));
  } finally { delete window.pywebview; }
});

test("assigning skips the base-layer Fn key", async () => {
  await useApp.getState().refresh();
  render(<Macros />);
  await userEvent.click(await screen.findByRole("button", { name: "New macro" }));
  await userEvent.type(screen.getByRole("textbox", { name: "Macro name" }), "A");
  await userEvent.click(screen.getByRole("button", { name: "Add key tap" }));
  expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Assign to key" })).toBeEnabled());
  await userEvent.click(screen.getByRole("button", { name: "Assign to key" }));
  await userEvent.click(await screen.findByRole("button", { name: "Fn" }));
  expect(screen.getByText(/Fn key can't hold a macro/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Assign" })).toBeDisabled();
});

test("save is blocked without a name and recording stops on unmount", async () => {
  const api = installApi();
  try {
    await useApp.getState().refresh();
    const { unmount } = render(<Macros />);
    await userEvent.click(await screen.findByRole("button", { name: "New macro" }));
    await userEvent.click(screen.getByRole("button", { name: "Add key tap" }));
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    await screen.findByRole("button", { name: "Stop recording" });
    expect(screen.getByRole("textbox", { name: "Macro name" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "New macro" })).toBeDisabled();
    unmount();
    await waitFor(() => expect(api.record_macro_stop).toHaveBeenCalledTimes(1));
  } finally { delete window.pywebview; }
});

test("unreadable macros offer clear all", async () => {
  const api = installApi();
  try {
    const real = api.get_state.getMockImplementation()!;
    api.get_state.mockImplementation(async () => ({ ...((await real()) as KbState), macros: null, macros_error: "Macro memory is corrupt" }));
    await useApp.getState().refresh();
    render(<Macros />);
    expect(await screen.findByText("Macro memory is corrupt")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear all macros" }));
    await userEvent.click(await screen.findByRole("button", { name: "Clear all" }));
    await waitFor(() => expect(api.clear_macros).toHaveBeenCalledTimes(1));
  } finally { delete window.pywebview; }
});
