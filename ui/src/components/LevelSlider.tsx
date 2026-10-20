import { useEffect, useState } from "react";
import { Slider } from "@/components/ui/slider";

interface Props { label: string; value: number | null | undefined; max: number; onCommit: (v: number) => void; disabled?: boolean }

export function LevelSlider({ label, value, max, onCommit, disabled }: Props) {
  const [v, setV] = useState(value ?? 0);
  useEffect(() => setV(value ?? 0), [value]);
  return (
    <div>
      <div className="mb-2.5 flex justify-between text-[13px]">
        <span>{label}</span><span className="tabular-nums text-muted">{value == null ? "—" : `${v} / ${max}`}</span>
      </div>
      <Slider aria-label={label} min={0} max={max} step={1} value={[v]} disabled={disabled || value == null}
        onValueChange={([n]) => setV(n)} onValueCommit={([n]) => n !== value && onCommit(n)} />
    </div>
  );
}
