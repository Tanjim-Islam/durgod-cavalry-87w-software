import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { useApp } from "@/state/app";
import { Keys } from "./Keys";

test("remap J on the Fn layer and see the mark", async () => {
  await useApp.getState().refresh();
  render(<Keys />);
  await userEvent.click(await screen.findByRole("radio", { name: "Fn layer" }));
  await userEvent.click(screen.getByRole("button", { name: "J" }));
  expect(screen.getByText("Now: Nothing")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("radio", { name: "Media" }));
  await userEvent.click(screen.getByRole("radio", { name: "Calculator" }));
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  await waitFor(() => expect(useApp.getState().state?.layers?.[1][45]).toEqual({ type: "consumer", usage: 0x192 }));
  expect(screen.getByText("Now: Calculator")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "J" })).toHaveAttribute("aria-description", "assigned");
});

test("base-layer Fn can't be remapped", async () => {
  await useApp.getState().refresh();
  render(<Keys />);
  await userEvent.click(await screen.findByRole("button", { name: "Fn" }));
  expect(screen.getByText(/can't be remapped/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();
});

test("reset layer asks first", async () => {
  await useApp.getState().refresh();
  render(<Keys />);
  await userEvent.click(await screen.findByRole("button", { name: "Reset layer" }));
  expect(await screen.findByRole("dialog")).toBeInTheDocument();
});

test("the Fn key is locked on the base layer and the WASD swap, not on the Fn layer", async () => {
  await useApp.getState().refresh();
  render(<Keys />);
  await userEvent.click(await screen.findByRole("radio", { name: "WASD swap" }));
  await userEvent.click(screen.getByRole("button", { name: "Fn" }));
  expect(screen.getByText(/can't be remapped/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("radio", { name: "Fn layer" }));
  await userEvent.click(screen.getByRole("button", { name: "Fn" }));
  await waitFor(() => expect(screen.queryByText(/can't be remapped/)).not.toBeInTheDocument());
  expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument();
});

test("marks say changed on the base layer", async () => {
  await useApp.getState().refresh();
  await useApp.getState().act("remap_key", 0, 45, { type: "consumer", usage: 0x192 });
  render(<Keys />);
  expect(await screen.findByRole("button", { name: "J" })).toHaveAttribute("aria-description", "changed");
});

test("first-run 2.4G state asks for the cable instead of blaming the layout", async () => {
  await useApp.getState().refresh();
  const s = useApp.getState().state!;
  useApp.setState({ state: { ...s, partial: true, layers: null, macros: null } });
  render(<Keys />);
  expect(screen.getByText("Connect the cable once so the app can read your keyboard")).toBeInTheDocument();
  expect(screen.queryByText(/Couldn't read the key layout/)).not.toBeInTheDocument();
});
