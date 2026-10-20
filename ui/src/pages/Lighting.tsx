import { useState } from "react";
import type { RGB } from "@/bridge/types";
import { Switch } from "@/components/ui/switch";
import { Card } from "@/components/Card";
import { EffectRow } from "@/components/EffectRow";
import { Keyboard } from "@/components/Keyboard";
import { LevelSlider } from "@/components/LevelSlider";
import { KeyPainterControls, PaintKeyboard } from "@/components/KeyPainter";
import { PageShell } from "@/components/PageShell";
import { PaletteEditor } from "@/components/PaletteEditor";
import { useKeyPainter } from "@/lib/useKeyPainter";
import { useApp } from "@/state/app";

export function Lighting() {
  const { state, act } = useApp();
  const l = state?.lighting;
  const off = !state?.connected || state.partial;
  const [paletteDraft, setPaletteDraft] = useState<{ effect: number; colors: RGB[] } | null>(null);
  const game = l?.effect === 18;
  const painter = useKeyPainter({ keyColors: state?.key_colors, disabled: off, active: game,
    onSave: (colors) => act("set_key_colors", colors) });
  // While a palette draft exists for this effect, the preview and swatches show it instead of the saved colors.
  const draft = l && paletteDraft?.effect === l.effect ? paletteDraft.colors : null;
  const palette = l && draft && state?.palette ? state.palette.map((g, i) => (i === l.effect ? draft : g)) : state?.palette;
  const group = l && palette ? palette[l.effect] ?? palette[0] : null;
  const editable = !off && !!l;
  const set = (k: string, v: unknown) => {
    const args: Record<string, unknown> = { effect: null, brightness: null, speed: null, color: null, direction: null, [k]: v };
    return act("set_lighting", args.effect, args.brightness, args.speed, args.color, args.direction);
  };
  return (
    <PageShell title="Lighting" meta={off ? "Connect the keyboard to change lighting" : "Saved on the keyboard"}
      keyboard={game && state?.key_colors
        ? <PaintKeyboard painter={painter} lighting={l} />
        : <Keyboard lighting={l} palette={palette} keyColors={state?.key_colors} />}>
      {state?.lighting_error && <p className="text-xs text-accent">{state.lighting_error}</p>}
      <Card title="Effect">
        <EffectRow effects={state?.effects ?? []} value={l?.effect} disabled={off} onChange={(id) => void set("effect", id)} />
      </Card>
      {l && (game ? (
        <Card title="Key colors">
          {state?.key_colors ? (
            <KeyPainterControls painter={painter} />
          ) : <p className="text-xs text-muted">{state?.key_colors_error || "Key colors aren't available yet."}</p>}
        </Card>
      ) : (
        <Card title="Palette">
          {state?.palette ? (
            <PaletteEditor key={l.effect} effect={l.effect} palette={state.palette} disabled={!editable}
              onSave={(effect, colors) => act("set_palette", effect, colors)} onDraft={(g) => setPaletteDraft(g ? { effect: l.effect, colors: g } : null)} />
          ) : <p className="text-xs text-muted">{state?.palette_error || "Palette isn't available yet."}</p>}
        </Card>
      ))}
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Card><LevelSlider label="Brightness" value={l?.brightness} max={4} disabled={off} onCommit={(v) => set("brightness", v)} /></Card>
        <Card><LevelSlider label="Speed" value={l?.speed} max={4} disabled={off} onCommit={(v) => set("speed", v)} /></Card>
        <Card title="Color">
          <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Color">
            {[...(group ?? []), null].map((c, i) => (
              <button key={i} type="button" role="radio" aria-checked={l?.color === i} aria-label={c ? `Color ${i + 1}` : "Multicolor"}
                disabled={off || l?.color == null} onClick={() => void set("color", i)}
                className={`size-6 rounded-full border border-ink/25 transition-transform hover:scale-110 ${l?.color === i
                  ? "ring-2 ring-ink ring-offset-2 ring-offset-surface" : ""}`}
                style={{ background: c ? `rgb(${c.join(",")})` : "conic-gradient(#f55,#fd5,#5d5,#5df,#55f,#f5f,#f55)" }} />
            ))}
          </div>
        </Card>
        <Card>
          <label className="flex items-center justify-between text-[13px]">Reverse direction
            <Switch aria-label="Reverse direction" checked={Boolean(l?.direction)} disabled={off || l?.direction == null}
              onCheckedChange={(v) => void set("direction", v)} />
          </label>
          <label className="mt-3 flex items-center justify-between text-[13px]">Keep lights on
            <Switch aria-label="Keep lights on" checked={Boolean(l?.keep_lights_on)} disabled={off}
              onCheckedChange={(v) => void act("set_keep_lights_on", v)} />
          </label>
        </Card>
      </div>
    </PageShell>
  );
}
