import { expect, test } from "vitest";
import type { Lighting, RGB } from "@/bridge/types";
import { brightnessOpacity, isAnimated, previewColor } from "./effects";

const base: Lighting = { effect: 1, brightness: 4, speed: 3, color: 0, direction: false, keep_lights_on: true };
const group = (n: number): RGB[] => Array.from({ length: 7 }, (_, i) => [n, i, 0] as RGB);
const palette: RGB[][] = Array.from({ length: 23 }, (_, i) => group(i));

test("no lighting or brightness 0 is unlit", () => {
  expect(previewColor(null, palette, 0)).toBe("transparent");
  expect(previewColor({ ...base, brightness: 0 }, palette, 0)).toBe("transparent");
});

test("palette color is indexed by effect then color", () => {
  expect(previewColor({ ...base, effect: 5, color: 2 }, palette, 0)).toBe("rgb(5, 2, 0)");
});

test("color 7 or null is multicolor, varying per slot", () => {
  const a = previewColor({ ...base, color: 7 }, palette, 1);
  expect(a).toMatch(/^hsl\(/);
  expect(a).not.toBe(previewColor({ ...base, color: 7 }, palette, 2));
  expect(previewColor({ ...base, color: null }, palette, 1)).toBe(a);
});

test("effect 18 uses per-key colors, defaulting to black", () => {
  const l = { ...base, effect: 18 };
  expect(previewColor(l, palette, 1, [[1, 2, 3], [4, 5, 6]])).toBe("rgb(4, 5, 6)");
  expect(previewColor(l, palette, 9, [[1, 2, 3]])).toBe("rgb(0, 0, 0)");
});

test("falls back to group 0, then to the accent color", () => {
  const sparse: RGB[][] = [group(9)];
  expect(previewColor({ ...base, effect: 5, color: 1 }, sparse, 0)).toBe("rgb(9, 1, 0)");
  expect(previewColor(base, null, 0)).toBe("rgb(255, 122, 69)");
});

test("animation and opacity helpers", () => {
  expect(isAnimated(1)).toBe(false);
  expect(isAnimated(18)).toBe(false);
  expect(isAnimated(2)).toBe(true);
  expect(brightnessOpacity(4)).toBe(1);
  expect(brightnessOpacity(1)).toBeLessThan(brightnessOpacity(4));
});
