import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { PaletteEditor } from "./PaletteEditor";

const group = [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0], [255, 0, 255], [0, 255, 255], [255, 255, 255]] as [number, number, number][];

test("edit a color, preview the draft, save it", async () => {
  const onSave = vi.fn(); const onDraft = vi.fn();
  render(<PaletteEditor effect={1} palette={[group, group]} onSave={onSave} onDraft={onDraft} />);
  fireEvent.input(screen.getByLabelText("Edit color 1"), { target: { value: "#ff7a45" } });
  expect(onDraft).toHaveBeenLastCalledWith([[255, 122, 69], ...group.slice(1)]);
  await userEvent.click(screen.getByRole("button", { name: "Save colors" }));
  expect(onSave).toHaveBeenCalledWith(1, [[255, 122, 69], ...group.slice(1)]);
});

test("discard drops the draft and reset loads the defaults", async () => {
  const onDraft = vi.fn();
  render(<PaletteEditor effect={1} palette={[group, group]} onSave={vi.fn()} onDraft={onDraft} />);
  expect(screen.getByRole("button", { name: "Save colors" })).toBeDisabled();
  fireEvent.input(screen.getByLabelText("Edit color 2"), { target: { value: "#101010" } });
  await userEvent.click(screen.getByRole("button", { name: "Discard" }));
  expect(onDraft).toHaveBeenLastCalledWith(null);
  expect(screen.getByLabelText("Edit color 2")).toHaveValue("#00ff00");
  await userEvent.click(screen.getByRole("button", { name: "Reset to defaults" }));
  expect(onDraft).toHaveBeenLastCalledWith(group);
});

test("disabled blocks editing", () => {
  render(<PaletteEditor effect={1} palette={[group, group]} onSave={vi.fn()} onDraft={vi.fn()} disabled />);
  expect(screen.getByLabelText("Edit color 1")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Reset to defaults" })).toBeDisabled();
});
