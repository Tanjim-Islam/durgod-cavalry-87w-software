import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { connectUpdates, useUpdate, type UpdateState } from "@/state/update";
import { UpdateBox, UpdateSettings } from "./UpdateBox";

const base: UpdateState = { status: "current", current: "1.0.2", latest: "1.0.2", url: "https://x/releases", progress: 0,
  error: null, installable: true };

test("the sidebar box shows up to date, then an available update with Install", async () => {
  const api = { install_update: vi.fn(async () => ({ ...base, status: "downloading", latest: "1.1.0" })) };
  window.pywebview = { api: api as never };
  useUpdate.setState({ update: base });
  const { rerender } = render(<UpdateBox />);
  expect(screen.getByText(/Up to date · v1.0.2/)).toBeInTheDocument();
  useUpdate.setState({ update: { ...base, status: "available", latest: "1.1.0" } });
  rerender(<UpdateBox />);
  expect(await screen.findByText("Update available")).toBeInTheDocument();
  expect(screen.getByText("v1.0.2 → v1.1.0")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Install" }));
  expect(api.install_update).toHaveBeenCalled();
  expect(await screen.findByRole("progressbar", { name: "Download progress" })).toBeInTheDocument();
});

test("a portable copy offers Download instead of Install", async () => {
  useUpdate.setState({ update: { ...base, status: "available", latest: "1.1.0", installable: false } });
  render(<UpdateBox />);
  expect(await screen.findByRole("button", { name: "Download" })).toBeInTheDocument();
});

test("engine update events reach the box", async () => {
  useUpdate.setState({ update: base });
  connectUpdates();
  render(<UpdateBox />);
  window.__cavalryEmit?.({ name: "update", payload: { ...base, status: "installing", latest: "1.1.0" } });
  expect(await screen.findByText("Installing update")).toBeInTheDocument();
});

test("settings shows the version and checks for updates on demand", async () => {
  const api = { check_update: vi.fn(async () => ({ ...base, status: "checking" })) };
  window.pywebview = { api: api as never };
  useUpdate.setState({ update: base });
  render(<UpdateSettings />);
  expect(screen.getByText("v1.0.2")).toBeInTheDocument();
  expect(screen.getByText("You're on the latest version.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Check for updates" }));
  expect(api.check_update).toHaveBeenCalled();
  expect(await screen.findByText("Checking for updates…")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Check for updates" })).toBeDisabled();
});
