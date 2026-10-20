import { useEffect, useRef, useState } from "react";
import type { RGB } from "@/bridge/types";
import { fromHex, toHex } from "@/lib/color";

export const DEFAULT_GROUP: RGB[] = [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0], [255, 0, 255], [0, 255, 255], [255, 255, 255]];

interface Props {
  effect: number; palette: RGB[][]; disabled?: boolean;
  onSave: (effect: number, colors: RGB[]) => unknown;
  onDraft: (group: RGB[] | null) => void;
}

const btn = "rounded-lg border border-line px-3 py-1.5 text-[13px] disabled:opacity-40";

export function PaletteEditor({ effect, palette, disabled, onSave, onDraft }: Props) {
  const saved = palette[effect] ?? palette[0] ?? DEFAULT_GROUP;
  const [draft, setDraft] = useState<RGB[] | null>(null);
  const shown = draft ?? saved;
  const draftRef = useRef(onDraft); draftRef.current = onDraft;
  // A draft never outlives the editor or the effect it was made for.
  useEffect(() => () => draftRef.current(null), []);
  const update = (next: RGB[] | null) => { setDraft(next); onDraft(next); };
  const save = async () => {
    if (!draft) return;
    if ((await onSave(effect, draft)) !== false) update(null);
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex gap-1.5" role="group" aria-label="Palette colors">
        {shown.map((c, i) => (
          <input key={i} type="color" aria-label={`Edit color ${i + 1}`} value={toHex(c)} disabled={disabled}
            onChange={(e) => update(shown.map((o, j) => (j === i ? fromHex(e.target.value) : o)))}
            className="size-7 cursor-pointer rounded-full border border-ink/25 bg-transparent p-0 disabled:cursor-not-allowed disabled:opacity-40 [&::-webkit-color-swatch-wrapper]:p-0 [&::-webkit-color-swatch]:rounded-full [&::-webkit-color-swatch]:border-0" />
        ))}
      </div>
      <div className="ml-auto flex gap-2">
        <button type="button" disabled={disabled} onClick={() => update(DEFAULT_GROUP.map((c) => [...c] as RGB))} className={btn}>Reset to defaults</button>
        <button type="button" disabled={disabled || !draft} onClick={() => update(null)} className={btn}>Discard</button>
        <button type="button" disabled={disabled || !draft} onClick={() => void save()}
          className="rounded-lg bg-accent px-3 py-1.5 text-[13px] font-medium text-on-accent disabled:opacity-40">Save colors</button>
      </div>
    </div>
  );
}
