import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import type { KbState } from "@/bridge/types";
import { deviceStatus } from "@/lib/status";
import { useApp } from "@/state/app";
import App from "@/App";
import { Flyout } from "@/pages/Flyout";
import { ErrorBoundary } from "./ErrorBoundary";
import { Notices } from "./Notices";
import { StatusScreen } from "./StatusScreen";

const base = { connected: false, link: null, partial: false, asleep: false, effects: [], key_names: {} } as KbState;

test("device status covers every connection state", () => {
  expect(deviceStatus(null).kind).toBe("starting");
  expect(deviceStatus(base).kind).toBe("none");
  expect(deviceStatus({ ...base, link: "wired" }).kind).toBe("connecting");
  expect(deviceStatus({ ...base, link: "radio", asleep: true }).kind).toBe("asleep");
  expect(deviceStatus({ ...base, link: "radio", problem: { code: "wrong_model", message: "m" } }))
    .toEqual({ kind: "wrong_model", detail: "m" });
  expect(deviceStatus({ ...base, connected: true, link: "radio", partial: true }).kind).toBe("partial");
  expect(deviceStatus({ ...base, connected: true, link: "wired" }).kind).toBe("ready");
});

test("each blocked state has its own screen", () => {
  const cases = [
    [{ kind: "none" }, "No keyboard found"], [{ kind: "connecting" }, "Connecting to your keyboard"],
    [{ kind: "asleep" }, "Keyboard isn't answering"], [{ kind: "wrong_model", detail: "model 0x99" }, "This isn't a Cavalry 87W"],
    [{ kind: "connect_failed", detail: "error 5" }, "Couldn't talk to the keyboard"], [{ kind: "lost", detail: "x" }, "Lost the keyboard"],
  ] as const;
  for (const [status, title] of cases) {
    const { unmount } = render(<StatusScreen status={status} />);
    expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    unmount();
  }
});

test("try again asks the engine to reconnect", async () => {
  const api = { retry_connect: vi.fn(async () => ({ ...base, connected: true, link: "wired" })), open_logs: vi.fn(async () => {}) };
  window.pywebview = { api: api as never };
  render(<StatusScreen status={{ kind: "connect_failed", detail: "cannot open keyboard" }} />);
  expect(screen.getByText("cannot open keyboard")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  await userEvent.click(screen.getByRole("button", { name: "Open log folder" }));
  expect(api.retry_connect).toHaveBeenCalled();
  expect(api.open_logs).toHaveBeenCalled();
});

test("keyboard pages show the status screen, settings stays usable", async () => {
  const wrong = { ...base, link: "radio", problem: { code: "wrong_model", message: "model 0x99" } };
  window.pywebview = { api: {
    get_state: vi.fn(async () => wrong), get_app_settings: vi.fn(async () => ({ theme: "dark", autostart: false })),
    list_profiles: vi.fn(async () => []), list_backups: vi.fn(async () => []),
  } as never };
  render(<App />);
  expect(await screen.findByRole("heading", { name: "This isn't a Cavalry 87W" })).toBeInTheDocument();
  expect(screen.getByText("model 0x99")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Settings" }));
  await waitFor(() => expect(screen.queryByRole("heading", { name: "This isn't a Cavalry 87W" })).not.toBeInTheDocument());
  expect(screen.getByRole("radio", { name: "Dark" })).toBeInTheDocument();
});

test("the flyout shows a compact status instead of controls", () => {
  useApp.setState({ state: { ...base } });
  render(<Flyout />);
  expect(screen.getByRole("heading", { name: "No keyboard found" })).toBeInTheDocument();
  expect(screen.queryByRole("switch", { name: "Keep lights on" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Quit" })).toBeInTheDocument();
});

test("notices can be dismissed; a pending change shows an info line", async () => {
  const api = { dismiss_notice: vi.fn(async () => ({ ...base, connected: true, link: "wired", notices: [] })) };
  window.pywebview = { api: api as never };
  useApp.setState({ state: { ...base, connected: true, link: "wired", pending: true, notices: [{ code: "mirror", message: "disk full" }] } });
  render(<Notices />);
  expect(screen.getByText(/waiting for the keyboard/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
  expect(api.dismiss_notice).toHaveBeenCalledWith("mirror");
});

test("a crashing screen shows a way out", () => {
  const Boom = () => { throw new Error("kaboom"); };
  vi.spyOn(console, "error").mockImplementation(() => {});
  render(<ErrorBoundary><Boom /></ErrorBoundary>);
  expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeInTheDocument();
  expect(screen.getByText("kaboom")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument();
});
