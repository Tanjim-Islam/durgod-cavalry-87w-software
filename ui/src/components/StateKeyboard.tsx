import { Keyboard } from "@/components/Keyboard";
import { useApp } from "@/state/app";

export function StateKeyboard() {
  const state = useApp((s) => s.state);
  return <Keyboard lighting={state?.lighting} palette={state?.palette} keyColors={state?.key_colors} />;
}
