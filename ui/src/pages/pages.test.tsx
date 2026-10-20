import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { useApp } from "@/state/app";
import { Shortcuts } from "./Shortcuts";
import { Profiles } from "./Profiles";
import { Settings } from "./Settings";
import { Flyout } from "./Flyout";

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
