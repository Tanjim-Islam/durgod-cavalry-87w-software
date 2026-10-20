import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { LevelSlider } from "./LevelSlider";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

const press = (el: HTMLElement, key = "ArrowRight", n = 1) => {
  for (let i = 0; i < n; i++) fireEvent.keyDown(el, { key });
};

test("a burst of key presses updates the label live and commits once", async () => {
  const onCommit = vi.fn();
  render(<LevelSlider label="Brightness" value={1} max={4} onCommit={onCommit} />);
  const thumb = screen.getByRole("slider", { name: "Brightness" });
  expect(screen.getByText("1 / 4")).toBeInTheDocument();
  press(thumb, "ArrowRight", 3);
  expect(screen.getByText("4 / 4")).toBeInTheDocument();
  expect(onCommit).not.toHaveBeenCalled();
  await act(() => vi.advanceTimersByTimeAsync(500));
  expect(onCommit).toHaveBeenCalledTimes(1);
  expect(onCommit).toHaveBeenCalledWith(4);
});

test("null value shows a dash and the slider is disabled", () => {
  render(<LevelSlider label="Speed" value={null} max={4} onCommit={() => {}} />);
  expect(screen.getByText("-")).toBeInTheDocument();
  expect(screen.getByRole("slider", { name: "Speed" })).toHaveAttribute("data-disabled");
});

test("a failed commit rolls the label back to the keyboard value", async () => {
  const onCommit = vi.fn().mockResolvedValue(false);
  render(<LevelSlider label="Speed" value={2} max={4} onCommit={onCommit} />);
  press(screen.getByRole("slider", { name: "Speed" }), "ArrowRight", 2);
  expect(screen.getByText("4 / 4")).toBeInTheDocument();
  await act(() => vi.advanceTimersByTimeAsync(500));
  expect(onCommit).toHaveBeenCalledWith(4);
  expect(screen.getByText("2 / 4")).toBeInTheDocument();
});
