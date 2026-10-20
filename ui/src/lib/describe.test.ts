import { expect, test } from "vitest";
import { describe as describeAction, isRemapped, naturalAction } from "./describe";

test("describes every action kind", () => {
  expect(describeAction({ type: "none" })).toBe("Nothing");
  expect(describeAction({ type: "key", hid: 0x04, mods: 0x03, high: false })).toBe("Left Ctrl + Left Shift + A");
  expect(describeAction({ type: "key", hid: 0, mods: 0x02, high: false })).toBe("Left Shift");
  expect(describeAction({ type: "consumer", usage: 0xe2 })).toBe("Mute");
  expect(describeAction({ type: "system", code: 0x16 })).toBe("Mac mode");
  expect(describeAction({ type: "lighting", a: 3, b: 1 })).toBe("Brightness up");
  expect(describeAction({ type: "macro", index: 0, mode: 1, count: 1 })).toBe("Macro 1");
  expect(describeAction({ type: "mouse", code: 3, b2: 1, b3: 0 })).toBe("Right click");
  expect(describeAction({ type: "fn" })).toBe("Fn");
});

test("natural base layer and remap detection", () => {
  expect(naturalAction(0)).toEqual({ type: "key", hid: 0x29, mods: 0, high: false });
  expect(naturalAction(59)).toEqual({ type: "fn" });
  expect(isRemapped(0, 45, { type: "key", hid: 0x0d, mods: 0, high: false })).toBe(false);
  expect(isRemapped(0, 45, { type: "consumer", usage: 0x192 })).toBe(true);
  expect(isRemapped(1, 45, { type: "none" })).toBe(false);
  expect(isRemapped(1, 12, { type: "consumer", usage: 0xe2 })).toBe(true);
});
