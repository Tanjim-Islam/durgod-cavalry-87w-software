import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { Keyboard } from "./Keyboard";

const lighting = { effect: 1, brightness: 4, speed: 3, color: 0, direction: false, keep_lights_on: true };
const palette = Array.from({ length: 23 }, () => [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0],
  [255, 0, 255], [0, 255, 255], [255, 255, 255]] as [number, number, number][]);

test("static effect paints keys with the palette color", () => {
  render(<Keyboard lighting={lighting} palette={palette} />);
  expect(screen.getByLabelText("Esc")).toHaveStyle({ "--glow": "rgb(255, 0, 0)" });
});

test("click reports the engine slot", async () => {
  const onKeyClick = vi.fn();
  render(<Keyboard lighting={lighting} palette={palette} onKeyClick={onKeyClick} />);
  await userEvent.click(screen.getByLabelText("J"));
  expect(onKeyClick).toHaveBeenCalledWith(45);
});

const opacity = (name: string) => parseFloat(screen.getByLabelText(name).style.opacity);

test("right-side modifiers are addressable and report their own slot", async () => {
  const onKeyClick = vi.fn();
  render(<Keyboard lighting={lighting} palette={palette} onKeyClick={onKeyClick} />);
  await userEvent.click(screen.getByLabelText("Right Shift"));
  expect(onKeyClick).toHaveBeenCalledWith(82);
  expect(screen.getByLabelText("Left Shift")).toBeInTheDocument();
});

test("preview without onKeyClick has no focusable caps", () => {
  const { container } = render(<Keyboard lighting={lighting} palette={palette} />);
  expect(screen.queryAllByRole("button")).toHaveLength(0);
  expect(container.querySelectorAll("button, [tabindex]")).toHaveLength(0);
  expect(screen.getByLabelText("Right Shift")).toBeInTheDocument();
});

test("interactive caps expose the selected key via aria-pressed", () => {
  render(<Keyboard lighting={lighting} palette={palette} onKeyClick={() => {}} selected={45} />);
  expect(screen.getByLabelText("J")).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByLabelText("K")).toHaveAttribute("aria-pressed", "false");
});

test("captions use a fixed light color, not the theme ink token", () => {
  render(<Keyboard lighting={lighting} palette={palette} />);
  const cap = screen.getByLabelText("Esc");
  expect(cap.className).not.toMatch(/ink/);
  expect(cap.style.color).toBe("rgba(255, 255, 255, 0.72)");
  expect(screen.getByLabelText("Backspace")).toHaveTextContent("Bksp");
});

test("static opacity follows brightness", () => {
  const { rerender } = render(<Keyboard lighting={{ ...lighting, brightness: 4 }} palette={palette} />);
  const full = opacity("Esc");
  rerender(<Keyboard lighting={{ ...lighting, brightness: 1 }} palette={palette} />);
  expect(opacity("Esc")).toBeLessThan(full);
});

test("animated effect at brightness 0 stays unlit and does not pulse", async () => {
  render(<Keyboard lighting={{ ...lighting, effect: 2, brightness: 0 }} palette={palette} />);
  const start = opacity("Esc");
  await new Promise((r) => setTimeout(r, 200));
  expect(opacity("Esc")).toBe(start);
  expect(screen.getByLabelText("Esc")).toHaveStyle({ "--glow": "transparent" });
});

test("animated effect pulses, then returns to the static opacity", async () => {
  const { rerender } = render(<Keyboard lighting={{ ...lighting, effect: 2 }} palette={palette} />);
  await waitFor(() => expect(opacity("Esc")).toBeLessThan(1));
  rerender(<Keyboard lighting={{ ...lighting, effect: 1 }} palette={palette} />);
  await waitFor(() => expect(opacity("Esc")).toBe(1));
});
