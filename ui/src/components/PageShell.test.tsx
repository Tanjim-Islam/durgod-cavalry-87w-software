import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Keyboard } from "./Keyboard";
import { PageShell } from "./PageShell";

test("page children never shrink, so tall pages scroll instead of collapsing the keyboard", () => {
  render(
    <PageShell title="T" keyboard={<Keyboard />}>
      <section data-testid="card">card</section>
    </PageShell>,
  );
  const column = screen.getByRole("heading", { name: "T" }).closest("header")!.parentElement!;
  expect(column.className).toMatch(/overflow-y-auto/);
  expect(column.className).toContain("[&>*]:shrink-0");
  expect(screen.getByRole("img", { name: "Keyboard lighting preview" }).className).toMatch(/(^|\s)shrink-0(\s|$)/);
});
