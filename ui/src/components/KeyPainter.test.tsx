import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { toast } from "sonner";
import { KeyPainter } from "./KeyPainter";
import { STALE_MSG } from "@/lib/useDraft";

vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { info: vi.fn(), error: vi.fn() }) }));

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
  fireEvent.pointerDown(screen.getByRole("button", { name: "Esc" }), { button: 0, buttons: 1 });
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

test("only the primary button paints", () => {
  render(<KeyPainter keyColors={blank()} onSave={vi.fn()} />);
  fireEvent.pointerDown(screen.getByRole("button", { name: "Esc" }), { button: 2, buttons: 2 });
  expect(screen.getByRole("button", { name: "Save colors" })).toBeDisabled();
});

test("a failed save keeps the draft", async () => {
  render(<KeyPainter keyColors={blank()} onSave={vi.fn(async () => false)} />);
  await userEvent.click(screen.getByRole("button", { name: "Fill all" }));
  await userEvent.click(screen.getByRole("button", { name: "Save colors" }));
  expect(screen.getByRole("button", { name: "Save colors" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Discard" })).toBeEnabled();
});

test("controls are locked while a save is in flight", async () => {
  let done!: (v: boolean) => void;
  render(<KeyPainter keyColors={blank()} onSave={() => new Promise<boolean>((r) => { done = r; })} />);
  await userEvent.click(screen.getByRole("button", { name: "Fill all" }));
  await userEvent.click(screen.getByRole("button", { name: "Save colors" }));
  expect(screen.getByRole("button", { name: "Fill all" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Discard" })).toBeDisabled();
  done(true);
  await waitFor(() => expect(screen.getByRole("button", { name: "Fill all" })).toBeEnabled());
});

test("a change on the keyboard drops the draft and says so", async () => {
  const { rerender } = render(<KeyPainter keyColors={blank()} onSave={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Fill all" }));
  const next = blank(); next[3] = [9, 9, 9];
  rerender(<KeyPainter keyColors={next} onSave={vi.fn()} />);
  expect(toast.info).toHaveBeenCalledWith(STALE_MSG);
  expect(screen.getByRole("button", { name: "Save colors" })).toBeDisabled();
});

test("discard still works while disabled", async () => {
  const { rerender } = render(<KeyPainter keyColors={blank()} onSave={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Fill all" }));
  rerender(<KeyPainter keyColors={blank()} onSave={vi.fn()} disabled />);
  expect(screen.getByRole("button", { name: "Discard" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Save colors" })).toBeDisabled();
});
