import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { ActionEditor } from "./ActionEditor";

const none = { type: "none" } as const;

test("build a Ctrl+Shift+A key combo", async () => {
  const onApply = vi.fn();
  render(<ActionEditor value={none} macros={[]} onApply={onApply} />);
  await userEvent.click(screen.getByRole("radio", { name: "Key" }));
  await userEvent.click(screen.getByRole("checkbox", { name: "Left Ctrl" }));
  await userEvent.click(screen.getByRole("checkbox", { name: "Left Shift" }));
  await userEvent.type(screen.getByRole("searchbox", { name: "Search keys" }), "A");
  await userEvent.click(screen.getByRole("radio", { name: "A" }));
  expect(screen.getByText("Will do: Left Ctrl + Left Shift + A")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(onApply).toHaveBeenCalledWith({ type: "key", hid: 0x04, mods: 0x03, high: false });
});

test("media, shortcut preset and macro modes", async () => {
  const onApply = vi.fn();
  render(<ActionEditor value={none} macros={[{ name: "Hi", events: [] }]} onApply={onApply} />);
  await userEvent.click(screen.getByRole("radio", { name: "Media" }));
  await userEvent.click(screen.getByRole("radio", { name: "Calculator" }));
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(onApply).toHaveBeenLastCalledWith({ type: "consumer", usage: 0x192 });
  await userEvent.click(screen.getByRole("radio", { name: "Shortcut" }));
  await userEvent.click(screen.getByRole("radio", { name: "Lock PC (Win+L)" }));
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(onApply).toHaveBeenLastCalledWith({ type: "key", hid: 0x0f, mods: 0x08, high: true });
  await userEvent.click(screen.getByRole("radio", { name: "Macro" }));
  await userEvent.click(screen.getByRole("radio", { name: "While held" }));
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(onApply).toHaveBeenLastCalledWith({ type: "macro", index: 0, mode: 2, count: 1 });
});

test("dangerous system actions are not offered", async () => {
  render(<ActionEditor value={none} macros={[]} onApply={() => {}} />);
  await userEvent.click(screen.getByRole("radio", { name: "System" }));
  expect(screen.queryByRole("radio", { name: "Factory reset" })).not.toBeInTheDocument();
  expect(screen.queryByRole("radio", { name: "Clear Bluetooth pairing" })).not.toBeInTheDocument();
  expect(screen.getByRole("radio", { name: "Mac mode" })).toBeInTheDocument();
});

test("F22+ shows the 2.4G-only note", async () => {
  render(<ActionEditor value={none} macros={[]} onApply={() => {}} />);
  await userEvent.click(screen.getByRole("radio", { name: "Key" }));
  await userEvent.type(screen.getByRole("searchbox", { name: "Search keys" }), "F24");
  await userEvent.click(screen.getByRole("radio", { name: "F24" }));
  expect(screen.getByText(/Works over 2.4G only/)).toBeInTheDocument();
});

test("opens preselected for lighting, consumer and shortcut values", () => {
  const { unmount } = render(<ActionEditor value={{ type: "lighting", a: 3, b: 1 }} macros={[]} onApply={() => {}} />);
  expect(screen.getByRole("radio", { name: "Brightness up" })).toHaveAttribute("aria-checked", "true");
  expect(screen.getByRole("button", { name: "Apply" })).toBeEnabled();
  unmount();
  const u2 = render(<ActionEditor value={{ type: "consumer", usage: 0x192 }} macros={[]} onApply={() => {}} />);
  expect(screen.getByRole("radio", { name: "Calculator" })).toHaveAttribute("aria-checked", "true");
  u2.unmount();
  render(<ActionEditor value={{ type: "key", hid: 0x0f, mods: 0x08, high: true }} macros={[]} onApply={() => {}} />);
  expect(screen.getByRole("radio", { name: "Lock PC (Win+L)" })).toHaveAttribute("aria-checked", "true");
});

test("a stored Factory reset is not preselected", () => {
  render(<ActionEditor value={{ type: "system", code: 0x04 }} macros={[]} onApply={() => {}} />);
  expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled();
});

test("mouse keeps its extra bytes when the code is unchanged", async () => {
  const onApply = vi.fn();
  render(<ActionEditor value={{ type: "mouse", code: 1, b2: 7, b3: 9 }} macros={[]} onApply={onApply} />);
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(onApply).toHaveBeenCalledWith({ type: "mouse", code: 1, b2: 7, b3: 9 });
});

test("an out-of-range macro index falls back to the first macro", async () => {
  const onApply = vi.fn();
  render(<ActionEditor value={{ type: "macro", index: 5, mode: 1, count: 1 }} macros={[{ name: "Hi", events: [] }]} onApply={onApply} />);
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(onApply).toHaveBeenCalledWith({ type: "macro", index: 0, mode: 1, count: 1 });
});

test("disabled locks every control", async () => {
  render(<ActionEditor value={none} macros={[]} onApply={() => {}} disabled />);
  await userEvent.click(screen.getByRole("radio", { name: "Key" }));
  expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled();
  expect(screen.getByRole("checkbox", { name: "Left Ctrl" })).toBeDisabled();
  expect(screen.getByRole("searchbox", { name: "Search keys" })).toBeDisabled();
  expect(screen.getByRole("radio", { name: "A" })).toBeDisabled();
});

test("key list is grouped and empty groups hide while searching", async () => {
  render(<ActionEditor value={{ type: "key", hid: 4, mods: 0, high: false }} macros={[]} onApply={() => {}} />);
  expect(screen.getByRole("group", { name: "Letters" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Numpad" })).toBeInTheDocument();
  await userEvent.type(screen.getByRole("searchbox", { name: "Search keys" }), "Enter");
  expect(screen.queryByRole("group", { name: "Letters" })).not.toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Editing" })).toBeInTheDocument();
});
