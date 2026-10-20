import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { useApp } from "@/state/app";
import { AssignDialog } from "./AssignDialog";

const open = async () => {
  await useApp.getState().refresh();
  await useApp.getState().act("save_macro", null, { name: "Hi", events: [] });
  render(<AssignDialog open macroIndex={0} onClose={() => {}} />);
};
const assign = () => screen.getByRole("button", { name: "Assign" });

test("the Fn key is refused on the base layer and the WASD swap, allowed on the Fn layer", async () => {
  await open();
  for (const layer of ["Base", "WASD swap"]) {
    await userEvent.click(await screen.findByRole("radio", { name: layer }));
    await userEvent.click(screen.getByRole("button", { name: "Fn" }));
    expect(screen.getByText("The Fn key can't hold a macro. Pick another key.")).toBeInTheDocument();
    expect(assign()).toBeDisabled();
  }
  await userEvent.click(screen.getByRole("radio", { name: "Fn layer" }));
  await userEvent.click(screen.getByRole("button", { name: "Fn" }));
  expect(assign()).toBeEnabled();
});

test("picked keys are marked as playing this macro", async () => {
  await open();
  await userEvent.click(await screen.findByRole("radio", { name: "Fn layer" }));
  await userEvent.click(screen.getByRole("button", { name: "J" }));
  await userEvent.click(assign());
  await open();
  await userEvent.click(await screen.findAllByRole("radio", { name: "Fn layer" }).then((r) => r[r.length - 1]));
  expect(screen.getAllByRole("button", { name: "J" }).at(-1)).toHaveAttribute("aria-description", "plays this macro");
});

test("first-run 2.4G state asks for the cable and disables assigning", async () => {
  await useApp.getState().refresh();
  const s = useApp.getState().state!;
  useApp.setState({ state: { ...s, partial: true, layers: null, macros: null } });
  render(<AssignDialog open macroIndex={0} onClose={() => {}} />);
  await userEvent.click(await screen.findByRole("button", { name: "Esc" }));
  expect(screen.getByText("Plug in the cable and press Fn + PrtSc (wired mode) once so the app can read your keys, macros and colors")).toBeInTheDocument();
  expect(assign()).toBeDisabled();
});
