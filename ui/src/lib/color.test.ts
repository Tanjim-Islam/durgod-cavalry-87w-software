import { expect, test } from "vitest";
import { fromHex, toHex } from "./color";

test("hex round trip", () => {
  expect(toHex([255, 122, 69])).toBe("#ff7a45");
  expect(toHex([0, 0, 0])).toBe("#000000");
  expect(fromHex("#ff7a45")).toEqual([255, 122, 69]);
  expect(fromHex(toHex([1, 2, 3]))).toEqual([1, 2, 3]);
});
