import { useMemo, useState } from "react";
import type { Action, Macro } from "@/bridge/types";
import { Segmented } from "@/components/Segmented";
import { describe } from "@/lib/describe";
import { CONSUMER, HID_KEYS, LIGHTING_FNS, MODIFIERS, MOUSE, NKRO_MAX, PRESETS, SYSTEM_OFFERED } from "@/lib/hid";

type Tab = "key" | "consumer" | "mouse" | "macro" | "shortcut" | "lighting" | "system" | "none";
const TABS: [Tab, string][] = [["key", "Key"], ["consumer", "Media"], ["mouse", "Mouse"], ["macro", "Macro"],
  ["shortcut", "Shortcut"], ["lighting", "Lighting"], ["system", "System"], ["none", "Disable"]];

function initialTab(a: Action): Tab {
  if (a.type === "key") return a.high ? "shortcut" : "key";
  return (["consumer", "mouse", "macro", "lighting", "system"] as Tab[]).includes(a.type as Tab) ? (a.type as Tab) : "key";
}

// A scrollable single-choice list.
function Options<T>({ label, items, value, onPick }: { label: string; items: [T, string][]; value: T | null; onPick: (v: T) => void }) {
  return (
    <div role="radiogroup" aria-label={label} className="no-scrollbar max-h-56 overflow-y-auto rounded-lg border border-line">
      {items.map(([v, name]) => (
        <button key={name} type="button" role="radio" aria-checked={value === v} aria-label={name} onClick={() => onPick(v)}
          className={`block w-full px-3 py-1.5 text-left text-[13px] ${value === v ? "bg-accent text-on-accent" : "hover:bg-surface-2"}`}>{name}</button>
      ))}
    </div>
  );
}

export function ActionEditor({ value, macros, onApply, disabled }: { value: Action; macros: Macro[]; onApply: (a: Action) => void; disabled?: boolean }) {
  const [tab, setTab] = useState<Tab>(initialTab(value));
  const [mods, setMods] = useState(value.type === "key" && !value.high ? value.mods : 0);
  const [hid, setHid] = useState<number | null>(value.type === "key" && !value.high ? value.hid || null : null);
  const [query, setQuery] = useState("");
  const [usage, setUsage] = useState<number | null>(value.type === "consumer" ? value.usage : null);
  const [mouse, setMouse] = useState<number | null>(value.type === "mouse" ? value.code : null);
  const [preset, setPreset] = useState<number | null>(null);
  const [light, setLight] = useState<number | null>(null);
  const [sys, setSys] = useState<number | null>(value.type === "system" ? value.code : null);
  const [macro, setMacro] = useState(value.type === "macro" ? value.index : 0);
  const [mode, setMode] = useState<"1" | "2" | "4">(value.type === "macro" ? (String(value.mode) as "1" | "2" | "4") : "1");
  const [count, setCount] = useState(value.type === "macro" ? value.count : 1);

  const action: Action | null = useMemo(() => {
    switch (tab) {
      case "key": return hid || mods ? { type: "key", hid: hid ?? 0, mods, high: false } : null;
      case "consumer": return usage != null ? { type: "consumer", usage } : null;
      case "mouse": return mouse != null ? { type: "mouse", code: mouse, b2: 1, b3: 0 } : null;
      case "shortcut": return preset != null ? PRESETS[preset].action : null;
      case "lighting": return light != null ? { type: "lighting", a: LIGHTING_FNS[light].a, b: LIGHTING_FNS[light].b } : null;
      case "system": return sys != null ? { type: "system", code: sys } : null;
      case "macro": return macros.length ? { type: "macro", index: macro, mode: Number(mode), count: mode === "1" ? count : 1 } : null;
      case "none": return { type: "none" };
    }
  }, [tab, hid, mods, usage, mouse, preset, light, sys, macro, mode, count, macros.length]);

  const keys = HID_KEYS.filter((k) => k.name.toLowerCase().includes(query.trim().toLowerCase()));
  return (
    <div className="flex flex-col gap-3">
      <div className="no-scrollbar overflow-x-auto"><Segmented label="Action type" value={tab} options={TABS} onChange={setTab} disabled={disabled} /></div>
      {tab === "key" && (<>
        <fieldset className="grid grid-cols-4 gap-1.5 text-[12px]"><legend className="sr-only">Modifiers</legend>
          {MODIFIERS.map((m) => (
            <label key={m.bit} className="flex items-center gap-1.5">
              <input type="checkbox" aria-label={m.name} checked={Boolean(mods & m.bit)} onChange={() => setMods(mods ^ m.bit)} className="accent-[var(--accent)]" />{m.name}
            </label>))}
        </fieldset>
        <input type="search" aria-label="Search keys" placeholder="Search keys" value={query} onChange={(e) => setQuery(e.target.value)}
          className="rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-[13px] outline-none focus:border-accent" />
        <Options label="Key" items={keys.map((k) => [k.hid, k.name])} value={hid} onPick={setHid} />
      </>)}
      {tab === "consumer" && <Options label="Media key" items={CONSUMER} value={usage} onPick={setUsage} />}
      {tab === "mouse" && <Options label="Mouse action" items={MOUSE} value={mouse} onPick={setMouse} />}
      {tab === "shortcut" && <Options label="Shortcut" items={PRESETS.map((p, i) => [i, p.name])} value={preset} onPick={setPreset} />}
      {tab === "lighting" && <Options label="Lighting function" items={LIGHTING_FNS.map((f, i) => [i, f.name])} value={light} onPick={setLight} />}
      {tab === "system" && <Options label="System function" items={SYSTEM_OFFERED} value={sys} onPick={setSys} />}
      {tab === "macro" && (macros.length === 0 ? <p className="text-[13px] text-muted">No macros yet. Create one on the Macros page.</p> : (<>
        <select aria-label="Macro" value={macro} onChange={(e) => setMacro(Number(e.target.value))}
          className="rounded-lg border border-line bg-surface-2 px-2 py-1.5 text-[13px]">
          {macros.map((m, i) => <option key={i} value={i}>{`${i + 1}. ${m.name}`}</option>)}
        </select>
        <Segmented label="Play mode" value={mode} options={[["1", "Once"], ["2", "While held"], ["4", "Toggle"]]} onChange={setMode} />
        {mode === "1" && <label className="flex items-center justify-between text-[13px]">Repeat
          <input type="number" aria-label="Repeat count" min={1} max={255} value={count}
            onChange={(e) => setCount(Math.min(255, Math.max(1, Number(e.target.value) || 1)))}
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
