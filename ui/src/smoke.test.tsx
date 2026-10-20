import { render, screen } from "@testing-library/react";
import { test, expect } from "vitest";

test("renders", () => {
  render(<h1 className="font-display">Cavalry</h1>);
  expect(screen.getByText("Cavalry")).toBeInTheDocument();
});
