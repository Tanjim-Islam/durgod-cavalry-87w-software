import { useEffect, useState } from "react";
import type { RGB } from "@/bridge/types";
import { useDraft } from "@/lib/useDraft";

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
