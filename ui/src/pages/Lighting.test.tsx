import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { Lighting } from "./Lighting";
import { useApp } from "@/state/app";

test("choosing an effect and toggling keep-lights-on go through the api", async () => {
  await useApp.getState().refresh();
  render(<Lighting />);
  await userEvent.click(await screen.findByRole("radio", { name: "Go with the Flow" }));
  await waitFor(() => expect(useApp.getState().state?.lighting?.effect).toBe(11));
  await userEvent.click(screen.getByRole("switch", { name: "Keep lights on" }));
  await waitFor(() => expect(useApp.getState().state?.lighting?.keep_lights_on).toBe(false));
});
