import { useEffect, useState } from "react";
import type { Lighting, RGB } from "@/bridge/types";
import { Keyboard } from "@/components/Keyboard";
import { fromHex, toHex } from "@/lib/color";
import { useDraft } from "@/lib/useDraft";

const btn = "rounded-lg border border-line px-3 py-1.5 text-[13px] disabled:opacity-40";

interface Options {
  keyColors: RGB[] | null | undefined; disabled?: boolean; active?: boolean;
  onSave: (colors: RGB[]) => unknown; onDraft?: (colors: RGB[] | null) => void;
}

// Painter state, separate from the views so a page can put the keyboard and the controls in different places.
export function useKeyPainter({ keyColors, disabled, active = true, onSave, onDraft }: Options) {
  const d = useDraft(keyColors, onDraft);
  const [brush, setBrush] = useState<RGB>([255, 122, 69]);
  const locked = !!disabled || d.saving;
  useEffect(() => { if (!active) d.discard(); }, [active]); // eslint-disable-line react-hooks/exhaustive-deps
  return {
    shown: d.shown, brush, setBrush, hasDraft: !!d.draft, saving: d.saving, disabled: !!disabled,
    paint: (slot: number) => { if (!locked) d.edit((c) => c.map((o, i) => (i === slot ? [...brush] as RGB : o))); },
    fill: (c: RGB) => d.edit((cur) => cur.map(() => [...c] as RGB)),
    discard: d.discard,
    save: () => void d.save(onSave),
  };
}
export type KeyPainterState = ReturnType<typeof useKeyPainter>;

// Painting needs to be visible, so a lights-off keyboard is previewed at full brightness.
export function PaintKeyboard({ painter, lighting }: { painter: KeyPainterState; lighting?: Lighting | null }) {
  const view: Lighting = { speed: null, color: null, direction: null, keep_lights_on: true,
    ...lighting, effect: 18, brightness: lighting?.brightness || 4 };
  const live = !painter.disabled && !painter.saving;
  return (
    <div className="select-none">
      <Keyboard lighting={view} keyColors={painter.shown}
        {...(live ? { onKeyClick: painter.paint, onKeyPaint: painter.paint } : {})} />
    </div>
  );
}

export function KeyPainterControls({ painter }: { painter: KeyPainterState }) {
  const locked = painter.disabled || painter.saving;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="flex items-center gap-2 text-[13px]">Brush
        <input type="color" aria-label="Brush color" value={toHex(painter.brush)} disabled={locked}
          onChange={(e) => painter.setBrush(fromHex(e.target.value))}
          className="size-7 cursor-pointer rounded-full border border-ink/25 bg-transparent p-0 disabled:cursor-not-allowed disabled:opacity-40 [&::-webkit-color-swatch-wrapper]:p-0 [&::-webkit-color-swatch]:rounded-full [&::-webkit-color-swatch]:border-0" />
      </label>
      <button type="button" disabled={locked} onClick={() => painter.fill(painter.brush)} className={btn}>Fill all</button>
      <button type="button" disabled={locked} onClick={() => painter.fill([0, 0, 0])} className={btn}>Clear all</button>
      <div className="ml-auto flex gap-2">
        <button type="button" disabled={!painter.hasDraft || painter.saving} onClick={painter.discard} className={btn}>Discard</button>
        <button type="button" disabled={locked || !painter.hasDraft} onClick={painter.save}
          className="rounded-lg bg-accent px-3 py-1.5 text-[13px] font-medium text-on-accent disabled:opacity-40">Save colors</button>
      </div>
    </div>
  );
}

interface Props {
  keyColors: RGB[]; disabled?: boolean; lighting?: Lighting | null;
  onSave: (colors: RGB[]) => unknown; onDraft?: (colors: RGB[] | null) => void;
}

// Standalone painter: its own keyboard plus controls.
export function KeyPainter({ keyColors, disabled, lighting, onSave, onDraft }: Props) {
  const painter = useKeyPainter({ keyColors, disabled, onSave, onDraft });
  return (
    <div className="flex flex-col gap-3">
      <KeyPainterControls painter={painter} />
      <PaintKeyboard painter={painter} lighting={lighting} />
    </div>
  );
}
