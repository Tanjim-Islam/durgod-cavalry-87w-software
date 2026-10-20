import { Switch } from "@/components/ui/switch";
import { Card } from "@/components/Card";
import { EffectRow } from "@/components/EffectRow";
import { Keyboard } from "@/components/Keyboard";
import { LevelSlider } from "@/components/LevelSlider";
import { PageShell } from "@/components/PageShell";
import { useApp } from "@/state/app";

export function Lighting() {
  const { state, act } = useApp();
  const l = state?.lighting;
  const off = !state?.connected || state.partial;
  const group = l && state?.palette ? state.palette[l.effect] ?? state.palette[0] : null;
  const set = (k: string, v: unknown) => {
    const args: Record<string, unknown> = { effect: null, brightness: null, speed: null, color: null, direction: null, [k]: v };
    void act("set_lighting", args.effect, args.brightness, args.speed, args.color, args.direction);
  };
  return (
    <PageShell title="Lighting" meta={off ? "Connect the keyboard to change lighting" : "Saved on the keyboard"}
      keyboard={<Keyboard lighting={l} palette={state?.palette} keyColors={state?.key_colors} />}>
      {state?.lighting_error && <p className="text-xs text-accent">{state.lighting_error}</p>}
      <Card title="Effect">
        <EffectRow effects={state?.effects ?? []} value={l?.effect} disabled={off} onChange={(id) => set("effect", id)} />
      </Card>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Card><LevelSlider label="Brightness" value={l?.brightness} max={4} disabled={off} onCommit={(v) => set("brightness", v)} /></Card>
        <Card><LevelSlider label="Speed" value={l?.speed} max={4} disabled={off} onCommit={(v) => set("speed", v)} /></Card>
        <Card title="Color">
          <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Color">
            {[...(group ?? []), null].map((c, i) => (
              <button key={i} type="button" role="radio" aria-checked={l?.color === i} aria-label={c ? `Color ${i + 1}` : "Multicolor"}
                disabled={off || l?.color == null} onClick={() => set("color", i)}
                className={`size-6 rounded-full border-2 transition-transform hover:scale-110
                  ${l?.color === i ? "border-ink" : "border-transparent"}`}
                style={{ background: c ? `rgb(${c.join(",")})` : "conic-gradient(#f55,#fd5,#5d5,#5df,#55f,#f5f,#f55)" }} />
            ))}
          </div>
        </Card>
        <Card>
          <label className="flex items-center justify-between text-[13px]">Reverse direction
            <Switch aria-label="Reverse direction" checked={Boolean(l?.direction)} disabled={off || l?.direction == null}
              onCheckedChange={(v) => set("direction", v)} />
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
