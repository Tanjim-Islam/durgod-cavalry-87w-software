import { expect, test } from "vitest";
import { KEYS } from "./layout";

test("87 keys with unique engine slots", () => {
  expect(KEYS).toHaveLength(87);
  expect(new Set(KEYS.map((k) => k.slot)).size).toBe(87);
});

test("known slots", () => {
  const by = Object.fromEntries(KEYS.map((k) => [k.label, k.slot]));
  expect(by.Esc).toBe(0); expect(by.J).toBe(45); expect(by.Fn).toBe(59);
  expect(by["\\"]).toBe(80); expect(by.Enter).toBe(81); expect(by.Right).toBe(101);
});
