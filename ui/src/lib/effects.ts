import type { Lighting, RGB } from "@/bridge/types";

export const STATIC_EFFECTS = new Set([1, 18]);
export const isAnimated = (effect: number) => !STATIC_EFFECTS.has(effect);

const rgb = ([r, g, b]: RGB) => `rgb(${r}, ${g}, ${b})`;

export function previewColor(l: Lighting | null | undefined, palette: RGB[][] | null | undefined,
                             slot: number, keyColors?: RGB[] | null): string {
  if (!l || l.brightness === 0) return "transparent";
  if (l.effect === 18 && keyColors) return rgb(keyColors[slot] ?? [0, 0, 0]);
  if (l.color === 7 || l.color == null) return `hsl(${(slot * 37) % 360} 90% 60%)`;
  const group = palette?.[l.effect] ?? palette?.[0];
  return rgb(group?.[l.color] ?? [255, 122, 69]);
}

export const brightnessOpacity = (b: number | null | undefined) => (b == null ? 1 : 0.35 + (b / 4) * 0.65);
