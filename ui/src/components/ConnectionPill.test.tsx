import { expect, test } from "vitest";
import type { KbState } from "@/bridge/types";
import { pillText } from "./ConnectionPill";

const base = { connected: true, link: "radio", partial: false, asleep: false } as KbState;

test("2.4G before the first cable read says what works", () => {
  expect(pillText({ ...base, partial: true })).toBe("2.4G · lighting and settings only");
  expect(pillText(base)).toBe("2.4G · connected");
});
