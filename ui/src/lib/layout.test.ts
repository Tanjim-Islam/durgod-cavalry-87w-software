import { expect, test } from "vitest";
import { KEYS } from "./layout";

const SLOTS: [string, number][] = [
    ["Esc", 0],   ["F1", 12],   ["F2", 18],   ["F3", 24],   ["F4", 30],   ["F5", 36],   ["F6", 42],
    ["F7", 48],   ["F8", 54],   ["F9", 60],   ["F10", 66],   ["F11", 72],   ["F12", 78],
    ["PrtSc", 84],   ["ScrLk", 90],   ["Pause", 96],   ["`", 1],   ["1", 7],   ["2", 13],
    ["3", 19],   ["4", 25],   ["5", 31],   ["6", 37],   ["7", 43],   ["8", 49],   ["9", 55],
    ["0", 61],   ["-", 67],   ["=", 73],   ["Backspace", 79],   ["Ins", 85],   ["Home", 91],
    ["PgUp", 97],   ["Tab", 2],   ["Q", 8],   ["W", 14],   ["E", 20],   ["R", 26],   ["T", 32],
    ["Y", 38],   ["U", 44],   ["I", 50],   ["O", 56],   ["P", 62],   ["[", 68],   ["]", 74],
    ["\\", 80],   ["Del", 86],   ["End", 92],   ["PgDn", 98],   ["Caps", 3],   ["A", 9],
    ["S", 15],   ["D", 21],   ["F", 27],   ["G", 33],   ["H", 39],   ["J", 45],   ["K", 51],
    ["L", 57],   [";", 63],   ["'", 69],   ["Enter", 81],   ["Shift", 4],   ["Z", 10],   ["X", 16],
    ["C", 22],   ["V", 28],   ["B", 34],   ["N", 40],   ["M", 46],   [",", 52],   [".", 58],
    ["/", 64],   ["Right Shift", 82],   ["Up", 94],   ["Ctrl", 5],   ["Win", 11],   ["Alt", 17],
    ["Space", 35],   ["Right Alt", 53],   ["Fn", 59],   ["Menu", 65],   ["Right Ctrl", 83],
    ["Left", 89],   ["Down", 95],   ["Right", 101],
];

test("87 keys with unique engine slots and names", () => {
  expect(KEYS).toHaveLength(87);
  expect(new Set(KEYS.map((k) => k.slot)).size).toBe(87);
  expect(new Set(KEYS.map((k) => k.name)).size).toBe(87);
});

test("every key maps to its engine slot", () => {
  expect(SLOTS).toHaveLength(87);
  expect(KEYS.map((k) => [k.name, k.slot])).toEqual(SLOTS);
});

test("known slots by caption", () => {
  const by = Object.fromEntries(KEYS.map((k) => [k.label, k.slot]));
  expect(by.Esc).toBe(0); expect(by.J).toBe(45); expect(by.Fn).toBe(59);
  expect(by["\\"]).toBe(80); expect(by.Enter).toBe(81); expect(by.Right).toBe(101);
});

test("right-side modifiers keep a short caption but a distinct name", () => {
  const right = KEYS.find((k) => k.slot === 82)!;
  expect([right.label, right.name]).toEqual(["Shift", "Right Shift"]);
  expect(KEYS.find((k) => k.slot === 79)!.label).toBe("Bksp");
});
