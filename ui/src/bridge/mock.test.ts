import { expect, test } from "vitest";
import { createMock } from "./mock";

test("mock editors round-trip like the engine", async () => {
  const m = createMock(() => {});
  const s0 = await m.get_state();
  expect(s0.layers![0][0]).toEqual({ type: "key", hid: 0x29, mods: 0, high: false });
  const s1 = await m.remap_key(1, 45, { type: "consumer", usage: 0x192 });
  expect(s1.layers![1][45]).toEqual({ type: "consumer", usage: 0x192 });
  const w = await m.remap_key(0, 45, { type: "key", hid: 0x73, mods: 0, high: false });
  expect(w.warning).toMatch(/cable/);
  const r = await m.save_macro(null, { name: "Hi", events: [] });
  expect(r.index).toBe(0);
  const s2 = await m.delete_macro(0);
  expect(s2.macros).toEqual([]);
  expect(await m.rename_profile("Default", "Main")).toEqual(["Main"]);
  await m.record_macro_start();
  expect((await m.record_macro_stop()).events.length).toBeGreaterThan(0);
});
