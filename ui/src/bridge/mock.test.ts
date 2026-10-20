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

test("mock refuses what the engine refuses", async () => {
  const m = createMock(() => {});
  const key = { type: "key", hid: 0x04, mods: 0, high: false } as const;
  for (const layer of [0, 3]) await expect(m.remap_key(layer, 59, key)).rejects.toThrow("can't be assigned");
  await m.remap_key(1, 59, key);
  for (const code of [0x04, 0x10]) await expect(m.remap_key(1, 45, { type: "system", code })).rejects.toThrow("can't be assigned");
  await m.remap_key(1, 45, { type: "system", code: 0x05 });
});

test("mock warns about cable-unsafe macro keys and checks profile names like the engine", async () => {
  const m = createMock(() => {});
  const ev = (code: number) => ({ kind: "key", code, release: false, delay_ms: 0 });
  expect((await m.save_macro(null, { name: "A", events: [ev(0x0b)] })).warning).toBeNull();
  expect((await m.save_macro(null, { name: "B", events: [ev(0x73)] })).warning).toMatch(/cable/);
  await m.save_profile("Work");
  await expect(m.rename_profile("Default", "work")).rejects.toThrow("already exists");
  expect(await m.rename_profile("Work", "WORK")).toEqual(["Default", "WORK"]);
});
