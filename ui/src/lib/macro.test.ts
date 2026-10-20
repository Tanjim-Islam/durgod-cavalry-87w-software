import { expect, test } from "vitest";
import { clampRepeat, eventLabel, heldAtEnd, macroBytes, tap } from "./macro";

test("size, labels and taps", () => {
  expect(macroBytes([{ name: "T", events: tap(0x68) }])).toBe(4 + 1 + 2 + 8);
  expect(eventLabel({ kind: "key", code: 0x04, release: false, delay_ms: 0 })).toBe("A down");
  expect(eventLabel({ kind: "modifier", code: 0xe1, release: true, delay_ms: 0 })).toBe("Left Shift up");
  expect(eventLabel({ kind: "mouse_button", code: 1, release: false, delay_ms: 0 })).toBe("Left click down");
  expect(tap(0x04)).toEqual([{ kind: "key", code: 4, release: false, delay_ms: 16 }, { kind: "key", code: 4, release: true, delay_ms: 16 }]);
});

test("held keys and repeat clamping", () => {
  const shiftDown = { kind: "modifier", code: 0xe1, release: false, delay_ms: 0 };
  expect(heldAtEnd([shiftDown, ...tap(0x04)])).toEqual(["Left Shift"]);
  expect(heldAtEnd([shiftDown, { ...shiftDown, release: true }, tap(0x04)[0]])).toEqual(["A"]);
  expect(clampRepeat("")).toBe(1);
  expect(clampRepeat("300")).toBe(255);
  expect(clampRepeat("12")).toBe(12);
});
