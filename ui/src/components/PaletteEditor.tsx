import type { RGB } from "@/bridge/types";
import { DEFAULT_GROUP, fromHex, toHex } from "@/lib/color";
import { useDraft } from "@/lib/useDraft";

interface Props {
  effect: number; palette: RGB[][]; disabled?: boolean;
  onSave: (effect: number, colors: RGB[]) => unknown;
  onDraft: (group: RGB[] | null) => void;
}

const btn = "rounded-lg border border-line px-3 py-1.5 text-[13px] disabled:opacity-40";

export function PaletteEditor({ effect, palette, disabled, onSave, onDraft }: Props) {
  const saved = palette[effect] ?? palette[0] ?? DEFAULT_GROUP;
  const d = useDraft(saved, onDraft);
  const shown = d.shown ?? saved;
  const locked = disabled || d.saving;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex gap-1.5" role="group" aria-label="Palette colors">
        {shown.map((c, i) => (
          <input key={i} type="color" aria-label={`Edit color ${i + 1}`} value={toHex(c)} disabled={locked}
            onChange={(e) => d.edit((cur) => cur.map((o, j) => (j === i ? fromHex(e.target.value) : o)))}
            className="size-7 cursor-pointer rounded-full border border-ink/25 bg-transparent p-0 disabled:cursor-not-allowed disabled:opacity-40 [&::-webkit-color-swatch-wrapper]:p-0 [&::-webkit-color-swatch]:rounded-full [&::-webkit-color-swatch]:border-0" />
        ))}
      </div>
      <div className="ml-auto flex gap-2">
        <button type="button" disabled={locked} onClick={() => d.edit(() => DEFAULT_GROUP.map((c) => [...c] as RGB))} className={btn}>Reset to defaults</button>
        <button type="button" disabled={!d.draft || d.saving} onClick={d.discard} className={btn}>Discard</button>
        <button type="button" disabled={locked || !d.draft} onClick={() => void d.save((colors) => onSave(effect, colors))}
          className="rounded-lg bg-accent px-3 py-1.5 text-[13px] font-medium text-on-accent disabled:opacity-40">Save colors</button>
      </div>
    </div>
  );
}
