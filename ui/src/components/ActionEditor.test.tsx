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
