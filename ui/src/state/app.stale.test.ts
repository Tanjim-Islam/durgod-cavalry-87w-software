import { expect, test, vi } from "vitest";

let release: (v: unknown) => void = () => {};
vi.mock("@/bridge/api", () => ({
  call: vi.fn((m: string) => m === "get_state"
    ? new Promise((r) => { release = r; })
    : Promise.resolve({ connected: true, lighting: { effect: 7 } })),
  onEvent: vi.fn(), windowAction: vi.fn(),
}));
import { useApp } from "./app";

test("a stale get_state can't overwrite a newer applied state", async () => {
  const slow = useApp.getState().refresh();
  await useApp.getState().act("set_lighting", 7);
  release({ connected: true, lighting: { effect: 1 } });
  await slow;
  expect(useApp.getState().state?.lighting?.effect).toBe(7);
});
