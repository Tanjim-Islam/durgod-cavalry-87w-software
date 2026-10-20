import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { Lighting } from "./Lighting";
import { useApp } from "@/state/app";

test("choosing an effect and toggling keep-lights-on go through the api", async () => {
  await useApp.getState().refresh();
  render(<Lighting />);
  await userEvent.click(await screen.findByRole("radio", { name: "Go with the Flow" }));
  await waitFor(() => expect(useApp.getState().state?.lighting?.effect).toBe(11));
  await userEvent.click(screen.getByRole("switch", { name: "Keep lights on" }));
  await waitFor(() => expect(useApp.getState().state?.lighting?.keep_lights_on).toBe(false));
});

test("every color swatch has a visible edge and only the selected one has the outer ring", async () => {
  await useApp.getState().refresh();
  render(<Lighting />);
  const swatches = await screen.findAllByRole("radio", { name: /^Color \d|^Multicolor$/ });
  expect(swatches.length).toBeGreaterThan(1);
  for (const s of swatches) expect(s.className).toContain("border-ink/25");
  const selected = swatches.filter((s) => s.getAttribute("aria-checked") === "true");
  for (const s of swatches) expect(/ring-2/.test(s.className)).toBe(selected.includes(s));
});

test("editing a palette color and saving updates the keyboard state", async () => {
  await useApp.getState().refresh();
  render(<Lighting />);
  await userEvent.click(await screen.findByRole("radio", { name: "Go with the Flow" }));
  await waitFor(() => expect(useApp.getState().state?.lighting?.effect).toBe(11));
  fireEvent.input(await screen.findByLabelText("Edit color 1"), { target: { value: "#123456" } });
  await userEvent.click(screen.getByRole("button", { name: "Save colors" }));
  await waitFor(() => expect(useApp.getState().state?.palette?.[11][0]).toEqual([18, 52, 86]));
  expect(useApp.getState().state?.palette?.[11]).toHaveLength(7);
});

test("switching effect drops the palette draft", async () => {
  await useApp.getState().refresh();
  render(<Lighting />);
  await userEvent.click(await screen.findByRole("radio", { name: "Breathing" }));
  fireEvent.input(await screen.findByLabelText("Edit color 1"), { target: { value: "#123456" } });
  expect(screen.getByLabelText("Edit color 1")).toHaveValue("#123456");
  await userEvent.click(screen.getByRole("radio", { name: "Dream Rainbow" }));
  await waitFor(() => expect(screen.getByLabelText("Edit color 1")).toHaveValue("#ff0000"));
  await userEvent.click(screen.getByRole("radio", { name: "Breathing" }));
  await waitFor(() => expect(screen.getByLabelText("Edit color 1")).toHaveValue("#ff0000"));
});

test("game mode paints from the page keyboard slot and saves 126 colors", async () => {
  await useApp.getState().refresh();
  render(<Lighting />);
  await userEvent.click(await screen.findByRole("radio", { name: "Game Mode" }));
  const esc = await screen.findByRole("button", { name: "Esc" });
  expect(esc.closest("section")).toBeNull();
  expect(screen.queryByLabelText("Keyboard lighting preview")).toBeNull();
  fireEvent.input(screen.getByLabelText("Brush color"), { target: { value: "#00ff00" } });
  await userEvent.click(esc);
  await userEvent.click(screen.getByRole("button", { name: "Save colors" }));
  await waitFor(() => expect(useApp.getState().state?.key_colors?.[0]).toEqual([0, 255, 0]));
  expect(useApp.getState().state?.key_colors).toHaveLength(126);
});
