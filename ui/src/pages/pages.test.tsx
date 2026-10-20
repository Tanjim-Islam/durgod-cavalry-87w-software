import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi, type Mock } from "vitest";
import { createMock } from "@/bridge/mock";
import type { KbState, ShortcutRow } from "@/bridge/types";
import { useApp } from "@/state/app";
import { Shortcuts } from "./Shortcuts";
import { Profiles } from "./Profiles";
import { Settings } from "./Settings";
import { Flyout } from "./Flyout";

type Api = Record<string, Mock>;

// Route the bridge through a spied copy of the mock engine.
function installApi(): Api {
  const base = createMock((e) => window.__cavalryEmit?.(e)) as unknown as Record<string, (...a: unknown[]) => Promise<unknown>>;
  const api: Api = {};
  for (const k of Object.keys(base)) api[k] = vi.fn(base[k]);
  window.pywebview = { api: api as never };
  return api;
}
const calls = (api: Api, name: string) => api[name].mock.calls.length;
const withState = (api: Api, patch: (s: KbState) => void) => {
  const real = api.get_state.getMockImplementation()!;
  api.get_state.mockImplementation(async () => { const s = (await real()) as KbState; patch(s); return s; });
};

afterEach(() => { delete window.pywebview; });

test("shortcuts are grouped and include the hidden Win/Mac keys", async () => {
  render(<Shortcuts />);
  const system = await screen.findByRole("region", { name: "System" });
  expect(await within(system).findByText("Mac mode (not in manual)")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Media" })).toBeInTheDocument();
});

test("save a profile and restore a backup with confirmation", async () => {
  await useApp.getState().refresh();
  render(<Profiles />);
  await userEvent.type(await screen.findByPlaceholderText("Profile name"), "Gaming");
  await userEvent.click(screen.getByRole("button", { name: "Save current" }));
  expect(await screen.findByText("Gaming")).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("button", { name: "Restore" })[0]);
  await userEvent.click(await screen.findByRole("button", { name: "Restore to keyboard" }));
  await waitFor(() => expect(useApp.getState().busy).toBe(false));
});

test("settings switch win/mac and theme", async () => {
  await useApp.getState().refresh();
  render(<Settings />);
  await userEvent.click(await screen.findByRole("radio", { name: "Mac" }));
  await waitFor(() => expect(useApp.getState().state?.settings?.win_mac).toBe("mac"));
  await userEvent.click(screen.getByRole("radio", { name: "Light" }));
  await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));
});

test("flyout has quick controls and app actions", async () => {
  await useApp.getState().refresh();
  render(<Flyout />);
  expect(await screen.findByRole("radiogroup", { name: "Effect" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open app" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Quit" })).toBeInTheDocument();
  expect(screen.getByRole("switch", { name: "Start with Windows" })).toBeInTheDocument();
});

test("a changed shortcut shows the current action and the factory label", async () => {
  const api = installApi();
  const row: ShortcutRow = { keys: "Fn + F1", group: "Media", label: "Mute", slot: 1, current: "Play/Pause",
    current_action: null, changed: true };
  api.get_shortcuts.mockImplementation(async () => [row]);
  render(<Shortcuts />);
  const media = await screen.findByRole("region", { name: "Media" });
  expect(await within(media).findByText("Play/Pause")).toBeInTheDocument();
  expect(within(media).getByText("Factory: Mute")).toBeInTheDocument();
});

test("restore_backup is sent only after confirming, and Cancel sends nothing", async () => {
  const api = installApi();
  await useApp.getState().refresh();
  render(<Profiles />);
  const restore = async () => (await screen.findAllByRole("button", { name: "Restore" }))[0];
  await userEvent.click(await restore());
  expect(await screen.findByText("Restore this backup to the keyboard?")).toBeInTheDocument();
  expect(calls(api, "restore_backup")).toBe(0);
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(calls(api, "restore_backup")).toBe(0);
  await userEvent.click(await restore());
  await userEvent.click(await screen.findByRole("button", { name: "Restore to keyboard" }));
  await waitFor(() => expect(calls(api, "restore_backup")).toBe(1));
});

test("saving over an existing profile name asks before overwriting", async () => {
  const api = installApi();
  await useApp.getState().refresh();
  render(<Profiles />);
  await screen.findByText("Default");
  await userEvent.type(screen.getByPlaceholderText("Profile name"), "default");
  await userEvent.click(screen.getByRole("button", { name: "Save current" }));
  expect(await screen.findByText("Overwrite default?")).toBeInTheDocument();
  expect(calls(api, "save_profile")).toBe(0);
  await userEvent.click(screen.getByRole("button", { name: "Overwrite" }));
  await waitFor(() => expect(api.save_profile).toHaveBeenCalledWith("default"));
});

test("apply and restore are disabled while the keyboard is not connected", async () => {
  installApi();
  await useApp.getState().refresh();
  useApp.setState({ state: { ...useApp.getState().state!, connected: false } });
  render(<Profiles />);
  expect(await screen.findByRole("button", { name: "Apply Default" })).toBeDisabled();
  for (const b of await screen.findAllByRole("button", { name: "Restore" })) expect(b).toBeDisabled();
});

test("flyout hides on blur and Esc, but Esc with the confirm open only closes the dialog", async () => {
  const api = installApi();
  await useApp.getState().refresh();
  render(<Flyout />);
  const restore = screen.getByRole("button", { name: "Restore" });
  await waitFor(() => expect(restore).toBeEnabled());
  fireEvent.blur(window);
  expect(calls(api, "hide_flyout")).toBe(1);
  await userEvent.keyboard("{Escape}");
  expect(calls(api, "hide_flyout")).toBe(2);

  await userEvent.click(restore);
  expect(await screen.findByRole("dialog")).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(calls(api, "hide_flyout")).toBe(2);
  expect(calls(api, "restore_backup")).toBe(0);
});

test("flyout reloads backups when it regains focus or becomes visible, and after applying a profile", async () => {
  const api = installApi();
  await useApp.getState().refresh();
  render(<Flyout />);
  await waitFor(() => expect(calls(api, "list_backups")).toBe(1));
  fireEvent.focus(window);
  await waitFor(() => expect(calls(api, "list_backups")).toBe(2));
  expect(calls(api, "list_profiles")).toBe(2);
  expect(calls(api, "get_app_settings")).toBe(2);

  document.dispatchEvent(new Event("visibilitychange"));
  await waitFor(() => expect(calls(api, "list_backups")).toBe(3));

  const select = screen.getByRole("combobox", { name: "Profile" });
  await waitFor(() => expect(select).toBeEnabled());
  await userEvent.selectOptions(select, "Default");
  await waitFor(() => expect(api.apply_profile).toHaveBeenCalledWith("Default"));
  await waitFor(() => expect(calls(api, "list_backups")).toBe(4));
});

test("settings show a non-listed sleep value as a readable custom option", async () => {
  const api = installApi();
  withState(api, (s) => { s.settings = { win_mac: "win", sleep: 12, debounce: 0 }; });
  await useApp.getState().refresh();
  render(<Settings />);
  expect(screen.getByRole("combobox", { name: "Sleep after" })).toHaveDisplayValue("6 min (custom)");
});

test("sleep select is disabled with a neutral placeholder before state loads", () => {
  installApi();
  useApp.setState({ state: null });
  render(<Settings />);
  const sel = screen.getByRole("combobox", { name: "Sleep after" });
  expect(sel).toBeDisabled();
  expect(sel).toHaveDisplayValue("—");
});

test("every page shows the keyboard preview", async () => {
  await useApp.getState().refresh();
  for (const page of [<Shortcuts key="s" />, <Profiles key="p" />, <Settings key="t" />]) {
    const { unmount } = render(page);
    expect(await screen.findByRole("img", { name: "Keyboard lighting preview" })).toBeInTheDocument();
    unmount();
  }
});
