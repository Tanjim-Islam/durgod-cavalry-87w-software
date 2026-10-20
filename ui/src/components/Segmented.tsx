import { motion } from "motion/react";

export function Segmented<T extends string>({ label, value, options, onChange, disabled }: {
  label: string; value: T | undefined; options: [T, string][]; onChange: (v: T) => void; disabled?: boolean }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-line bg-surface-2 p-0.5">
      {options.map(([v, text]) => (
        <button key={v} type="button" role="radio" aria-checked={value === v} aria-label={text} disabled={disabled}
          onClick={() => onChange(v)} className={`relative rounded-md px-3 py-1 text-[13px] ${value === v ? "text-on-accent" : "text-muted"}`}>
          {value === v && <motion.span layoutId={`seg-${label}`} className="absolute inset-0 rounded-md bg-accent" />}
          <span className="relative">{text}</span>
        </button>
      ))}
    </div>
  );
}
