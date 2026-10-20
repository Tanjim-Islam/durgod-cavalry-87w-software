import { useMemo, useState } from "react";
import type { Action, Macro } from "@/bridge/types";
import { Segmented } from "@/components/Segmented";
import { describe } from "@/lib/describe";
import { CONSUMER, HID_KEYS, LIGHTING_FNS, MODIFIERS, MOUSE, NKRO_MAX, PRESETS, SYSTEM_OFFERED } from "@/lib/hid";
import { clampRepeat } from "@/lib/macro";

type Tab = "key" | "consumer" | "mouse" | "macro" | "shortcut" | "lighting" | "system" | "none";
const TABS: [Tab, string][] = [["key", "Key"], ["consumer", "Media"], ["mouse", "Mouse"], ["macro", "Macro"],
  ["shortcut", "Shortcut"], ["lighting", "Lighting"], ["system", "System"], ["none", "Disable"]];

function initialTab(a: Action): Tab {
  if (a.type === "key") return a.high ? "shortcut" : "key";
  return (["consumer", "mouse", "macro", "lighting", "system"] as Tab[]).includes(a.type as Tab) ? (a.type as Tab) : "key";
}

// A scrollable single-choice list.
type Group<T> = { title?: string; items: [T, string][] };

function Options<T>({ label, groups, value, onPick, disabled }: { label: string; groups: Group<T>[]; value: T | null; onPick: (v: T) => void; disabled?: boolean }) {
  return (
    <div role="radiogroup" aria-label={label} className="no-scrollbar max-h-56 overflow-y-auto rounded-lg border border-line">
      {groups.map((g, i) => (
        <div key={g.title ?? i} role={g.title ? "group" : undefined} aria-label={g.title}>
          {g.title && <div aria-hidden="true" className="sticky top-0 bg-surface-2 px-3 py-1 text-[11px] font-medium uppercase tracking-wide text-muted">{g.title}</div>}
          {g.items.map(([v, name]) => (
            <button key={name} type="button" role="radio" aria-checked={value === v} aria-label={name} disabled={disabled} onClick={() => onPick(v)}
              className={`block w-full px-3 py-1.5 text-left text-[13px] disabled:opacity-50 ${value === v ? "bg-accent text-on-accent" : "hover:bg-surface-2"}`}>{name}</button>
          ))}
        </div>
      ))}
    </div>
  );
}
const flat = <T,>(items: [T, string][]): Group<T>[] => [{ items }];

export function ActionEditor({ value, macros, onApply, disabled }: { value: Action; macros: Macro[]; onApply: (a: Action) => void; disabled?: boolean }) {
  const [tab, setTab] = useState<Tab>(initialTab(value));
  const [mods, setMods] = useState(value.type === "key" && !value.high ? value.mods : 0);
  const [hid, setHid] = useState<number | null>(value.type === "key" && !value.high ? value.hid || null : null);
  const [query, setQuery] = useState("");
  const [usage, setUsage] = useState<number | null>(value.type === "consumer" ? value.usage : null);
  const [mouse, setMouse] = useState<number | null>(value.type === "mouse" ? value.code : null);
  const [preset, setPreset] = useState<number | null>(() => {
    if (value.type !== "key" || !value.high) return null;
    const i = PRESETS.findIndex((p) => p.action.type === "key" && p.action.hid === value.hid && p.action.mods === value.mods);
    return i < 0 ? null : i;
  });
  const [light, setLight] = useState<number | null>(() => {
    if (value.type !== "lighting") return null;
    const i = LIGHTING_FNS.findIndex((f) => f.a === value.a && f.b === value.b);
    return i < 0 ? null : i;
  });
  const [sys, setSys] = useState<number | null>(value.type === "system" && SYSTEM_OFFERED.some(([c]) => c === value.code) ? value.code : null);
  const [macro, setMacro] = useState(value.type === "macro" && value.index < macros.length ? value.index : 0);
  const [mode, setMode] = useState<"1" | "2" | "4">(value.type === "macro" ? (String(value.mode) as "1" | "2" | "4") : "1");
  const [countText, setCountText] = useState(String(value.type === "macro" ? value.count : 1));
  const count = clampRepeat(countText);

  const action: Action | null = useMemo(() => {
    switch (tab) {
      case "key": return hid || mods ? { type: "key", hid: hid ?? 0, mods, high: false } : null;
      case "consumer": return usage != null ? { type: "consumer", usage } : null;
      case "mouse": return mouse != null ? (value.type === "mouse" && value.code === mouse ? { ...value } : { type: "mouse", code: mouse, b2: 1, b3: 0 }) : null;
      case "shortcut": return preset != null ? PRESETS[preset].action : null;
      case "lighting": return light != null ? { type: "lighting", a: LIGHTING_FNS[light].a, b: LIGHTING_FNS[light].b } : null;
      case "system": return sys != null ? { type: "system", code: sys } : null;
      case "macro": return macros.length ? { type: "macro", index: macro, mode: Number(mode), count: mode === "1" ? count : 1 } : null;
      case "none": return { type: "none" };
    }
  }, [tab, hid, mods, usage, mouse, preset, light, sys, macro, mode, count, macros.length, value]);

  const q = query.trim().toLowerCase();
  const keyGroups: Group<number>[] = [];
  for (const k of HID_KEYS) {
    if (!k.name.toLowerCase().includes(q)) continue;
    let g = keyGroups.find((x) => x.title === k.group);
    if (!g) keyGroups.push(g = { title: k.group, items: [] });
    g.items.push([k.hid, k.name]);
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="no-scrollbar overflow-x-auto"><Segmented label="Action type" value={tab} options={TABS} onChange={setTab} disabled={disabled} /></div>
      {tab === "key" && (<>
        <fieldset className="grid grid-cols-4 gap-1.5 text-[12px]"><legend className="sr-only">Modifiers</legend>
          {MODIFIERS.map((m) => (
            <label key={m.bit} className="flex items-center gap-1.5">
              <input type="checkbox" aria-label={m.name} checked={Boolean(mods & m.bit)} disabled={disabled} onChange={() => setMods(mods ^ m.bit)} className="accent-[var(--accent)]" />{m.name}
            </label>))}
        </fieldset>
        <input type="search" aria-label="Search keys" placeholder="Search keys" value={query} disabled={disabled} onChange={(e) => setQuery(e.target.value)}
          className="rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-[13px] outline-none focus:border-accent" />
        <Options label="Key" groups={keyGroups} value={hid} onPick={setHid} disabled={disabled} />
      </>)}
      {tab === "consumer" && <Options label="Media key" groups={flat(CONSUMER)} value={usage} onPick={setUsage} disabled={disabled} />}
      {tab === "mouse" && <Options label="Mouse action" groups={flat(MOUSE)} value={mouse} onPick={setMouse} disabled={disabled} />}
      {tab === "shortcut" && <Options label="Shortcut" groups={flat(PRESETS.map((p, i): [number, string] => [i, p.name]))} value={preset} onPick={setPreset} disabled={disabled} />}
      {tab === "lighting" && <Options label="Lighting function" groups={flat(LIGHTING_FNS.map((f, i): [number, string] => [i, f.name]))} value={light} onPick={setLight} disabled={disabled} />}
      {tab === "system" && <Options label="System function" groups={flat(SYSTEM_OFFERED)} value={sys} onPick={setSys} disabled={disabled} />}
      {tab === "macro" && (macros.length === 0 ? <p className="text-[13px] text-muted">No macros yet. Create one on the Macros page.</p> : (<>
        <select aria-label="Macro" value={macro} disabled={disabled} onChange={(e) => setMacro(Number(e.target.value))}
          className="rounded-lg border border-line bg-surface-2 px-2 py-1.5 text-[13px]">
          {macros.map((m, i) => <option key={i} value={i}>{`${i + 1}. ${m.name}`}</option>)}
        </select>
        <Segmented label="Play mode" value={mode} options={[["1", "Once"], ["2", "While held"], ["4", "Toggle"]]} onChange={setMode} disabled={disabled} />
        {mode === "1" && <label className="flex items-center justify-between text-[13px]">Repeat
          <input type="number" aria-label="Repeat count" min={1} max={255} value={countText} disabled={disabled}
            onChange={(e) => setCountText(e.target.value)} onBlur={() => setCountText(String(count))}
            className="w-20 rounded-md border border-line bg-surface-2 px-2 py-1 text-right" /></label>}
      </>))}
      {tab === "none" && <p className="text-[13px] text-muted">The key will do nothing.</p>}
      <div className="flex items-center justify-between gap-3 border-t border-line pt-3 text-[13px]">
        <span className="text-muted">{action ? `Will do: ${describe(action)}` : "Pick an action"}
          {action?.type === "key" && action.hid > NKRO_MAX && <span className="block text-accent">Works over 2.4G only (not over the cable)</span>}</span>
        <button type="button" disabled={!action || disabled} onClick={() => action && onApply(action)}
          className="rounded-lg bg-accent px-3 py-1.5 font-medium text-on-accent disabled:opacity-40">Apply</button>
      </div>
    </div>
  );
}
