import type { RGB } from "@/bridge/types";

export const toHex = ([r, g, b]: RGB) => "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");

export const fromHex = (hex: string): RGB => {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
