import { render, screen } from "@testing-library/react";
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
