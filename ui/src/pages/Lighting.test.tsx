import { render, screen, waitFor } from "@testing-library/react";
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
