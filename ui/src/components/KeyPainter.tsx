import { useEffect, useRef, useState } from "react";
import type { Lighting, RGB } from "@/bridge/types";
import { Keyboard } from "@/components/Keyboard";
import { fromHex, toHex } from "@/lib/color";

interface Props {
  keyColors: RGB[]; disabled?: boolean;
  onSave: (colors: RGB[]) => unknown;
  onDraft?: (colors: RGB[] | null) => void;
}

// The painter is its own preview, so it always shows the colors at full brightness.
const PAINT_VIEW: Lighting = { effect: 18, brightness: 4, speed: null, color: null, direction: null, keep_lights_on: true };
const btn = "rounded-lg border border-line px-3 py-1.5 text-[13px] disabled:opacity-40";

export function KeyPainter({ keyColors, disabled, onSave, onDraft }: Props) {
  const [draft, setDraft] = useState<RGB[] | null>(null);
  const [brush, setBrush] = useState<RGB>([255, 122, 69]);
  const shown = draft ?? keyColors;
  const draftRef = useRef(onDraft); draftRef.current = onDraft;
  useEffect(() => () => draftRef.current?.(null), []);
  // Latest colors, updated synchronously so fast drags never paint from a stale render.
  const cur = useRef(shown); cur.current = shown;
  const update = (next: RGB[] | null) => { setDraft(next); onDraft?.(next); if (next) cur.current = next; };
  const paint = (slot: number) => {
    if (disabled) return;
    update(cur.current.map((c, i) => (i === slot ? [...brush] as RGB : c)));
  };
  const fill = (c: RGB) => update(shown.map(() => [...c] as RGB));
  const save = async () => {
    if (draft && (await onSave(draft)) !== false) update(null);
  };
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-[13px]">Brush
          <input type="color" aria-label="Brush color" value={toHex(brush)} disabled={disabled}
            onChange={(e) => setBrush(fromHex(e.target.value))}
            className="size-7 cursor-pointer rounded-full border border-ink/25 bg-transparent p-0 disabled:cursor-not-allowed disabled:opacity-40 [&::-webkit-color-swatch-wrapper]:p-0 [&::-webkit-color-swatch]:rounded-full [&::-webkit-color-swatch]:border-0" />
        </label>
        <button type="button" disabled={disabled} onClick={() => fill(brush)} className={btn}>Fill all</button>
        <button type="button" disabled={disabled} onClick={() => fill([0, 0, 0])} className={btn}>Clear all</button>
        <div className="ml-auto flex gap-2">
          <button type="button" disabled={disabled || !draft} onClick={() => update(null)} className={btn}>Discard</button>
          <button type="button" disabled={disabled || !draft} onClick={() => void save()}
            className="rounded-lg bg-accent px-3 py-1.5 text-[13px] font-medium text-on-accent disabled:opacity-40">Save colors</button>
        </div>
      </div>
      <div className="overflow-x-auto no-scrollbar select-none">
        <Keyboard lighting={PAINT_VIEW} keyColors={shown} onKeyClick={paint} onKeyPaint={paint} />
      </div>
    </div>
  );
}
