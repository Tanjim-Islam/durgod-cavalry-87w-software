import { describe, expect, test, vi, beforeEach } from "vitest";

vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { error: vi.fn() }) }));
import { toast } from "sonner";
import { handleResult, useApp } from "./app";

beforeEach(() => useApp.setState({ state: null, busy: false, pending: 0 }));

describe("app store", () => {
  test("refresh loads state from the bridge", async () => {
    await useApp.getState().refresh();
    expect(useApp.getState().state?.lighting?.effect).toBe(1);
  });

  test("act stores the returned state", async () => {
    await useApp.getState().act("set_lighting", 11, null, null, null, null);
    expect(useApp.getState().state?.lighting?.effect).toBe(11);
  });

  test("act shows ApiError text as an error toast and keeps old state", async () => {
    await useApp.getState().refresh();
    const before = useApp.getState().state;
    await useApp.getState().act("apply_profile", "Nope");
    expect(toast.error).toHaveBeenCalledWith("No such profile");
    expect(useApp.getState().state).toBe(before);
  });

  test("warning in a result becomes a toast and state is kept from the result", () => {
    handleResult({ connected: true, link: "radio", warning: "careful" });
    expect(toast).toHaveBeenCalledWith("careful");
    expect(useApp.getState().state?.connected).toBe(true);
    handleResult(["Default"]);
    expect(useApp.getState().state?.connected).toBe(true);
  });

  test("run returns the raw result and busy tracks overlapping calls", async () => {
    const a = useApp.getState().run<{ index: number }>("save_macro", null, { name: "X", events: [] });
    const b = useApp.getState().run("get_state");
    expect(useApp.getState().pending).toBe(2);
    expect((await a)?.index).toBeTypeOf("number");
    await b;
    expect(useApp.getState().pending).toBe(0);
    expect(useApp.getState().busy).toBe(false);
  });
});
