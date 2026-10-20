import { motion, useReducedMotion } from "motion/react";
import type { Lighting, RGB } from "@/bridge/types";
import { KEYS, KB_HEIGHT, KB_WIDTH } from "@/lib/layout";
import { brightnessOpacity, isAnimated, previewColor } from "@/lib/effects";

interface Props {
  lighting?: Lighting | null; palette?: RGB[][] | null; keyColors?: RGB[] | null;
  selected?: number | null; onKeyClick?: (slot: number) => void; unit?: number;
}

// Caps are dark in both themes, so captions use a fixed light color rather than the theme ink.
const CAPTION = "rgba(255, 255, 255, 0.72)";

export function Keyboard({ lighting, palette, keyColors, selected, onKeyClick, unit = 30 }: Props) {
  const reduce = useReducedMotion();
  const o = brightnessOpacity(lighting?.brightness);
  const pulse = !!lighting && isAnimated(lighting.effect) && lighting.brightness !== 0 && !reduce;
  const gap = 3;
  return (
    <div className="relative mx-auto rounded-2xl border border-line bg-[#141414] p-3"
         style={{ width: KB_WIDTH * unit + 24, height: KB_HEIGHT * unit + 24 }}
         {...(onKeyClick ? {} : { role: "img", "aria-label": "Keyboard lighting preview" })}>
      {KEYS.map((k) => {
        const props = {
          "aria-label": k.name,
          className: "absolute rounded-[6px] border text-[10px] leading-none font-medium transition-colors " +
            (selected === k.slot ? "border-accent ring-2 ring-accent/60" : "border-white/5"),
          style: { left: 12 + k.x * unit, top: 12 + k.y * unit, width: k.w * unit - gap, height: unit - gap,
                   color: CAPTION, background: "color-mix(in oklab, var(--glow) 22%, #232323)",
                   boxShadow: "inset 0 -2px 0 rgba(0,0,0,.35), 0 0 10px color-mix(in oklab, var(--glow) 35%, transparent)",
                   opacity: o, ["--glow" as string]: previewColor(lighting, palette, k.slot, keyColors) },
          animate: { opacity: pulse ? [0.55 * o, o, 0.55 * o] : o },
          transition: pulse ? { duration: 2.4, repeat: Infinity, delay: (k.x + k.y) * 0.06 } : { duration: 0.2 },
        };
        const text = k.w >= 1 && k.label.length <= 6 ? k.label : "";
        return onKeyClick ? (
          <motion.button key={k.slot} type="button" aria-pressed={selected === k.slot}
            onClick={() => onKeyClick(k.slot)} whileHover={{ y: -1 }} whileTap={{ y: 1 }} {...props}>
            {text}
          </motion.button>
        ) : (
          <motion.div key={k.slot} aria-hidden="true" {...props}>{text}</motion.div>
        );
      })}
    </div>
  );
}
