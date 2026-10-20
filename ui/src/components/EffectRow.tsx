import { useEffect, useRef } from "react";
import { motion } from "motion/react";

interface Props { effects: { id: number; name: string }[]; value: number | null | undefined; onChange: (id: number) => void; disabled?: boolean }

export function EffectRow({ effects, value, onChange, disabled }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.querySelector<HTMLElement>("[aria-checked=true]")
      ?.scrollIntoView?.({ inline: "center", block: "nearest", behavior: "smooth" });
  }, [value]);
  return (
    <div ref={ref} role="radiogroup" aria-label="Effect"
      className="no-scrollbar fade-right overflow-x-auto overscroll-x-contain"
      onWheel={(e) => { if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) e.currentTarget.scrollLeft += e.deltaY; }}>
      <div className="flex w-max gap-1.5 pr-10">
        {effects.map((e) => {
          const on = e.id === value;
          return (
            <button key={e.id} type="button" role="radio" aria-checked={on} disabled={disabled}
              onClick={() => onChange(e.id)}
              className={`relative whitespace-nowrap rounded-full border px-3 py-1.5 text-xs transition-colors
                ${on ? "border-accent text-on-accent" : "border-line text-muted hover:text-ink hover:border-[#444]"}`}>
              {on && <motion.span layoutId="effect-chip" className="absolute inset-0 rounded-full bg-accent"
                transition={{ type: "spring", stiffness: 500, damping: 38 }} />}
              <span className="relative">{e.name}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
