import { useEffect } from "react";
import { Switch } from "@/components/ui/switch";
import { Card } from "@/components/Card";
import { LevelSlider } from "@/components/LevelSlider";
import { Segmented } from "@/components/Segmented";
import { PageShell } from "@/components/PageShell";
import { StateKeyboard } from "@/components/StateKeyboard";
import { useApp } from "@/state/app";

function sleepLabel(units: number) {
  const secs = units * 30;
  if (secs < 60) return `${secs} s`;
  return secs % 60 === 0 ? `${secs / 60} min` : `${Math.floor(secs / 60)} min ${secs % 60} s`;
}

const SLEEP = [[1, "30 s"], [2, "1 min"], [4, "2 min"], [6, "3 min"], [10, "5 min"], [20, "10 min"], [40, "20 min"]] as const;

export function Settings() {
  const { state, settings, act, setAppSettings, loadSettings } = useApp();
  useEffect(() => { void loadSettings(); }, [loadSettings]);
  const s = state?.settings;
  const off = !state?.connected || state.partial;
  return (
    <PageShell title="Settings" meta="Keyboard and app preferences" keyboard={<StateKeyboard />}>
      <div className="grid gap-3 lg:grid-cols-2">
        <Card title="Layout">
          <Segmented label="Win or Mac" value={s?.win_mac} disabled={off}
            options={[["win", "Windows"], ["mac", "Mac"]]} onChange={(v) => void act("set_settings", v, null, null)} />
        </Card>
        <Card title="Sleep">
          <label className="flex items-center justify-between text-[13px]">Keep lights on
            <Switch aria-label="Keep lights on" checked={s?.sleep === 0} disabled={off} onCheckedChange={(v) => void act("set_keep_lights_on", v)} />
          </label>
          <label className="mt-3 flex items-center justify-between text-[13px]">Sleep after
            <select aria-label="Sleep after" disabled={off || !s || s.sleep === 0} value={s?.sleep ?? ""}
              onChange={(e) => void act("set_settings", null, Number(e.target.value), null)}
              className="rounded-md border border-line bg-surface-2 px-2 py-1 text-[13px] disabled:opacity-40">
              {!s && <option value="">—</option>}
              {s?.sleep === 0 && <option value={0}>Never</option>}
              {s && s.sleep !== 0 && !SLEEP.some(([v]) => v === s.sleep) && <option value={s.sleep}>{sleepLabel(s.sleep)} (custom)</option>}
              {SLEEP.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </label>
        </Card>
        <Card><LevelSlider label="Debounce" value={s?.debounce} max={4} disabled={off} onCommit={(v) => act("set_settings", null, null, v)} /></Card>
        <Card title="Appearance">
          <Segmented label="Theme" value={settings.theme}
            options={[["dark", "Dark"], ["light", "Light"], ["system", "System"]]} onChange={(v) => void setAppSettings({ theme: v })} />
        </Card>
        <Card>
          <label className="flex items-center justify-between text-[13px]">Start with Windows
            <Switch aria-label="Start with Windows" checked={settings.autostart} onCheckedChange={(v) => void setAppSettings({ autostart: v })} />
          </label>
        </Card>
        <Card title="About">
          <p className="text-[13px] text-muted">Durgod Cavalry 87W · model 0x7B · {state?.link === "wired" ? "Cable" : state?.link === "radio" ? "2.4G" : "Not connected"}</p>
        </Card>
      </div>
    </PageShell>
  );
}
