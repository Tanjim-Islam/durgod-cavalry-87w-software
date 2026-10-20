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
  expect(screen.getByRole("button", { name: "J" })).toHaveAttribute("aria-description", "remapped");
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
