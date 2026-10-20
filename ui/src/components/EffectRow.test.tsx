import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { EffectRow } from "./EffectRow";

const effects = Array.from({ length: 17 }, (_, i) => ({ id: i + 1, name: `E${i + 1}` }));

test("renders all 17 chips in one row and reports clicks", async () => {
  const onChange = vi.fn();
  render(<EffectRow effects={effects} value={1} onChange={onChange} />);
  expect(screen.getAllByRole("radio")).toHaveLength(17);
  await userEvent.click(screen.getByRole("radio", { name: "E11" }));
  expect(onChange).toHaveBeenCalledWith(11);
  expect(screen.getByRole("radio", { name: "E1" })).toHaveAttribute("aria-checked", "true");
});

test("vertical wheel scrolls horizontally", () => {
  render(<EffectRow effects={effects} value={1} onChange={() => {}} />);
  const scroller = screen.getByRole("radiogroup");
  fireEvent.wheel(scroller, { deltaY: 120 });
  expect(scroller.scrollLeft).toBe(120);
});

test("horizontal-dominant wheel is left alone, vertical is prevented", () => {
  render(<EffectRow effects={effects} value={1} onChange={() => {}} />);
  const scroller = screen.getByRole("radiogroup");
  expect(fireEvent.wheel(scroller, { deltaY: 120 })).toBe(false);
  expect(fireEvent.wheel(scroller, { deltaX: 120, deltaY: 5 })).toBe(true);
});
