import { useRef } from "react";
import { motion, useReducedMotion } from "motion/react";
import type { Lighting, RGB } from "@/bridge/types";
import { KEYS, KB_HEIGHT, KB_WIDTH } from "@/lib/layout";
import { brightnessOpacity, isAnimated, previewColor } from "@/lib/effects";

interface Props {
  lighting?: Lighting | null; palette?: RGB[][] | null; keyColors?: RGB[] | null;
  selected?: number | null; marks?: Set<number>; onKeyClick?: (slot: number) => void; unit?: number;
  // Drag painting: primary-button pointer down, plus drag-over while the button is held (touch and pen included).
  onKeyPaint?: (slot: number) => void;
}

// Caps are dark in both themes, so captions use a fixed light color rather than the theme ink.
const CAPTION = "rgba(255, 255, 255, 0.72)";

export function Keyboard({ lighting, palette, keyColors, selected, marks, onKeyClick, unit = 30, onKeyPaint }: Props) {
  const reduce = useReducedMotion();
  const lastPainted = useRef<number | null>(null);
  const o = brightnessOpacity(lighting?.brightness);
  const pulse = !!lighting && isAnimated(lighting.effect) && lighting.brightness !== 0 && !reduce;
  const gap = 3;
  // Touch and pen keep their pointer captured, so enter events never fire; find the key under the finger instead.
  const paintUnderPointer = (e: React.PointerEvent) => {
    if (e.pointerType === "mouse" || e.buttons !== 1 || !document.elementFromPoint) return;
    const slot = document.elementFromPoint(e.clientX, e.clientY)?.closest<HTMLElement>("[data-slot]")?.dataset.slot;
    if (slot == null || Number(slot) === lastPainted.current) return;
    lastPainted.current = Number(slot);
    onKeyPaint?.(Number(slot));
  };
  return (
    <div className="relative mx-auto shrink-0 rounded-2xl border border-line bg-[#141414] p-3"
         style={{ width: KB_WIDTH * unit + 24, height: KB_HEIGHT * unit + 24, ...(onKeyPaint ? { touchAction: "none" } : {}) }}
         {...(onKeyClick ? {} : { role: "img", "aria-label": "Keyboard lighting preview" })}
         {...(onKeyPaint ? { onPointerMove: paintUnderPointer, onPointerUp: () => { lastPainted.current = null; } } : {})}>
      {KEYS.map((k) => {
        const props = {
          "aria-label": k.name, "data-slot": k.slot,
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
        const dot = marks?.has(k.slot) ? <span aria-hidden="true" className="absolute right-1 top-1 size-1.5 rounded-full bg-accent" /> : null;
        return onKeyClick ? (
          <motion.button key={k.slot} type="button" aria-pressed={selected === k.slot}
            onClick={() => onKeyClick(k.slot)} whileHover={{ y: -1 }} whileTap={{ y: 1 }}
            {...(onKeyPaint ? {
              onPointerDown: (e: React.PointerEvent) => { if (e.button === 0) { lastPainted.current = k.slot; onKeyPaint(k.slot); } },
              onPointerEnter: (e: React.PointerEvent) => { if (e.buttons === 1) onKeyPaint(k.slot); },
            } : {})}
            {...(marks?.has(k.slot) ? { "aria-description": "remapped" } : {})} {...props}>
            {text}{dot}
          </motion.button>
        ) : (
          <motion.div key={k.slot} aria-hidden="true" {...props}>{text}{dot}</motion.div>
        );
      })}
    </div>
  );
}
