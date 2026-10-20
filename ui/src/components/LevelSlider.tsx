import { useEffect, useMemo, useRef, useState } from "react";
import { Slider } from "@/components/ui/slider";
import { debounce } from "@/lib/debounce";

type Commit = (v: number) => Promise<boolean> | boolean | void;
interface Props { label: string; value: number | null | undefined; max: number; onCommit: Commit; disabled?: boolean }

export function LevelSlider({ label, value, max, onCommit, disabled }: Props) {
  const [v, setV] = useState(value ?? 0);
  useEffect(() => setV(value ?? 0), [value]);

  const latest = useRef({ value, onCommit });
  latest.current = { value, onCommit };
  // One write per burst of changes (drag release or held arrow key); roll back if it fails.
  const commit = useMemo(() => debounce((n: number) => {
    const { value: cur, onCommit: fn } = latest.current;
    if (n === cur) return;
    void Promise.resolve(fn(n)).then((ok) => { if (ok === false) setV(latest.current.value ?? 0); });
  }, 400), []);

  return (
    <div>
      <div className="mb-2.5 flex justify-between text-[13px]">
        <span>{label}</span><span className="tabular-nums text-muted">{value == null ? "-" : `${v} / ${max}`}</span>
      </div>
      <Slider aria-label={label} min={0} max={max} step={1} value={[v]} disabled={disabled || value == null}
        onValueChange={([n]) => setV(n)} onValueCommit={([n]) => commit(n)} />
    </div>
  );
}
