import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { KeyPainter } from "./KeyPainter";

const blank = () => Array.from({ length: 126 }, () => [0, 0, 0] as [number, number, number]);

test("paint keys, fill, save 126 colors", async () => {
  const onSave = vi.fn();
  render(<KeyPainter keyColors={blank()} onSave={onSave} onDraft={() => {}} />);
  fireEvent.input(screen.getByLabelText("Brush color"), { target: { value: "#00ff00" } });
  await userEvent.click(screen.getByRole("button", { name: "Esc" }));
  await userEvent.click(screen.getByRole("button", { name: "Save colors" }));
  const saved = onSave.mock.calls[0][0];
  expect(saved).toHaveLength(126);
  expect(saved[0]).toEqual([0, 255, 0]);
  expect(saved[45]).toEqual([0, 0, 0]);
});

test("dragging with the button held paints, hovering alone does not", () => {
  const onSave = vi.fn();
  render(<KeyPainter keyColors={blank()} onSave={onSave} onDraft={() => {}} />);
  fireEvent.input(screen.getByLabelText("Brush color"), { target: { value: "#0000ff" } });
  fireEvent.pointerEnter(screen.getByRole("button", { name: "F1" }), { buttons: 0 });
  fireEvent.pointerDown(screen.getByRole("button", { name: "Esc" }), { buttons: 1 });
  fireEvent.pointerEnter(screen.getByRole("button", { name: "J" }), { buttons: 1 });
  fireEvent.click(screen.getByRole("button", { name: "Save colors" }));
  const saved = onSave.mock.calls[0][0];
  expect(saved[0]).toEqual([0, 0, 255]);
  expect(saved[45]).toEqual([0, 0, 255]);
  expect(saved[12]).toEqual([0, 0, 0]);
});

test("fill all, clear all and discard", async () => {
  const onDraft = vi.fn();
  render(<KeyPainter keyColors={blank()} onSave={vi.fn()} onDraft={onDraft} />);
  fireEvent.input(screen.getByLabelText("Brush color"), { target: { value: "#ff0000" } });
  await userEvent.click(screen.getByRole("button", { name: "Fill all" }));
  expect(onDraft.mock.lastCall![0].every((c: number[]) => c[0] === 255)).toBe(true);
  await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
  expect(onDraft.mock.lastCall![0].every((c: number[]) => c.every((v) => v === 0))).toBe(true);
  await userEvent.click(screen.getByRole("button", { name: "Discard" }));
  expect(onDraft).toHaveBeenLastCalledWith(null);
});
