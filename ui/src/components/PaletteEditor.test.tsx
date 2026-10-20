import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { toast } from "sonner";
import { PaletteEditor } from "./PaletteEditor";
import { STALE_MSG } from "@/lib/useDraft";

vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { info: vi.fn(), error: vi.fn() }) }));

const group = [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0], [255, 0, 255], [0, 255, 255], [255, 255, 255]] as [number, number, number][];

test("edit a color, preview the draft, save it", async () => {
  const onSave = vi.fn(); const onDraft = vi.fn();
  render(<PaletteEditor effect={1} palette={[group, group]} onSave={onSave} onDraft={onDraft} />);
  fireEvent.input(screen.getByLabelText("Edit color 1"), { target: { value: "#ff7a45" } });
  expect(onDraft).toHaveBeenLastCalledWith([[255, 122, 69], ...group.slice(1)]);
  await userEvent.click(screen.getByRole("button", { name: "Save colors" }));
  expect(onSave).toHaveBeenCalledWith(1, [[255, 122, 69], ...group.slice(1)]);
  expect(onSave.mock.calls[0][1]).toHaveLength(7);
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

test("a failed save keeps the draft", async () => {
  const onDraft = vi.fn();
  render(<PaletteEditor effect={1} palette={[group, group]} onSave={vi.fn(async () => false)} onDraft={onDraft} />);
  fireEvent.input(screen.getByLabelText("Edit color 1"), { target: { value: "#101010" } });
  await userEvent.click(screen.getByRole("button", { name: "Save colors" }));
  expect(screen.getByLabelText("Edit color 1")).toHaveValue("#101010");
  expect(screen.getByRole("button", { name: "Save colors" })).toBeEnabled();
  expect(onDraft).not.toHaveBeenLastCalledWith(null);
});

test("controls are locked while a save is in flight", async () => {
  let done!: (v: boolean) => void;
  const onSave = vi.fn(() => new Promise<boolean>((r) => { done = r; }));
  render(<PaletteEditor effect={1} palette={[group, group]} onSave={onSave} onDraft={vi.fn()} />);
  fireEvent.input(screen.getByLabelText("Edit color 1"), { target: { value: "#101010" } });
  await userEvent.click(screen.getByRole("button", { name: "Save colors" }));
  expect(screen.getByLabelText("Edit color 1")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Save colors" })).toBeDisabled();
  done(true);
  await waitFor(() => expect(screen.getByLabelText("Edit color 1")).toBeEnabled());
});

test("a change on the keyboard drops the draft and says so", () => {
  const onDraft = vi.fn();
  const { rerender } = render(<PaletteEditor effect={1} palette={[group, group]} onSave={vi.fn()} onDraft={onDraft} />);
  fireEvent.input(screen.getByLabelText("Edit color 1"), { target: { value: "#101010" } });
  const other = [[1, 2, 3], ...group.slice(1)] as typeof group;
  rerender(<PaletteEditor effect={1} palette={[group, other]} onSave={vi.fn()} onDraft={onDraft} />);
  expect(toast.info).toHaveBeenCalledWith(STALE_MSG);
  expect(onDraft).toHaveBeenLastCalledWith(null);
  expect(screen.getByLabelText("Edit color 1")).toHaveValue("#010203");
});

test("a change to another effect group does not drop the draft", () => {
  const { rerender } = render(<PaletteEditor effect={1} palette={[group, group]} onSave={vi.fn()} onDraft={vi.fn()} />);
  fireEvent.input(screen.getByLabelText("Edit color 1"), { target: { value: "#101010" } });
  rerender(<PaletteEditor effect={1} palette={[[...group.slice(1), group[0]], group]} onSave={vi.fn()} onDraft={vi.fn()} />);
  expect(screen.getByLabelText("Edit color 1")).toHaveValue("#101010");
});

test("a keyboard change during a save that fails still drops the draft", async () => {
  let done!: (v: boolean) => void;
  const onSave = vi.fn(() => new Promise<boolean>((r) => { done = r; }));
  const { rerender } = render(<PaletteEditor effect={1} palette={[group, group]} onSave={onSave} onDraft={vi.fn()} />);
  fireEvent.input(screen.getByLabelText("Edit color 1"), { target: { value: "#101010" } });
  await userEvent.click(screen.getByRole("button", { name: "Save colors" }));
  const other = [[1, 2, 3], ...group.slice(1)] as typeof group;
  rerender(<PaletteEditor effect={1} palette={[group, other]} onSave={onSave} onDraft={vi.fn()} />);
  vi.mocked(toast.info).mockClear();
  done(false);
  await waitFor(() => expect(toast.info).toHaveBeenCalledWith(STALE_MSG));
  expect(screen.getByLabelText("Edit color 1")).toHaveValue("#010203");
});
