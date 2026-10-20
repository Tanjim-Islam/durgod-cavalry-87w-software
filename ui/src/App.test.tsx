import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import App from "./App";

test("sidebar navigates between pages with the connection pill shown", async () => {
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Lighting" })).toBeInTheDocument();
  expect(await screen.findByText("2.4G · connected")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Shortcuts" }));
  expect(await screen.findByRole("heading", { name: "Shortcuts" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Keys/ })).toBeDisabled();
});
