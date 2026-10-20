import { motion, useReducedMotion } from "motion/react";
import type { Lighting, RGB } from "@/bridge/types";
import { KEYS, KB_HEIGHT, KB_WIDTH } from "@/lib/layout";
import { brightnessOpacity, isAnimated, previewColor } from "@/lib/effects";

interface Props {
  lighting?: Lighting | null; palette?: RGB[][] | null; keyColors?: RGB[] | null;
  selected?: number | null; onKeyClick?: (slot: number) => void; unit?: number;
}

export function Keyboard({ lighting, palette, keyColors, selected, onKeyClick, unit = 30 }: Props) {
  const reduce = useReducedMotion();
  const animate = lighting && isAnimated(lighting.effect) && !reduce;
  const gap = 3;
  return (
    <div className="relative mx-auto rounded-2xl border border-line bg-[color-mix(in_oklab,var(--bg)_70%,black)] p-3"
         style={{ width: KB_WIDTH * unit + 24, height: KB_HEIGHT * unit + 24 }}>
      {KEYS.map((k) => {
        const glow = previewColor(lighting, palette, k.slot, keyColors);
        return (
          <motion.button key={k.slot} type="button" aria-label={k.label} onClick={() => onKeyClick?.(k.slot)}
            className={"absolute rounded-[6px] border text-[10px] leading-none font-medium text-ink/70 " +
              "transition-colors " + (selected === k.slot ? "border-accent ring-2 ring-accent/60" : "border-white/5")}
            style={{ left: 12 + k.x * unit, top: 12 + k.y * unit, width: k.w * unit - gap, height: unit - gap,
                     background: "color-mix(in oklab, var(--glow) 22%, #232323)",
                     boxShadow: "inset 0 -2px 0 rgba(0,0,0,.35), 0 0 10px color-mix(in oklab, var(--glow) 35%, transparent)",
                     opacity: brightnessOpacity(lighting?.brightness),
                     ["--glow" as string]: glow }}
            animate={animate ? { opacity: [0.55, 1, 0.55] } : undefined}
            transition={animate ? { duration: 2.4, repeat: Infinity, delay: (k.x + k.y) * 0.06 } : undefined}
            whileHover={onKeyClick ? { y: -1 } : undefined} whileTap={onKeyClick ? { y: 1 } : undefined}>
            {k.w >= 1 && k.label.length <= 6 ? k.label : ""}
          </motion.button>
        );
      })}
    </div>
  );
}
