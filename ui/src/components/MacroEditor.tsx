import { useState } from "react";
import { ArrowDown, ArrowUp, X } from "lucide-react";
import type { Macro, MacroEvent } from "@/bridge/types";
import { HID_KEYS, NKRO_MAX } from "@/lib/hid";
import { DELAY_MAX, MOUSE_BUTTONS, NAME_MAX, click, eventLabel, tap, totalMs } from "@/lib/macro";

const GROUPS = [...new Set(HID_KEYS.map((k) => k.group))];
const field = "rounded-lg border border-line bg-surface-2 px-2 py-1.5 text-[13px] outline-none focus:border-accent disabled:opacity-50";
const icon = "rounded-md p-1 text-muted hover:bg-surface-2 hover:text-ink disabled:opacity-30";

const fmt = (ms: number) => (ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(2)} s`);

// Controlled editor for one macro: name, ordered events with delays, and quick inserts.
export function MacroEditor({ macro, onChange, disabled }: { macro: Macro; onChange: (m: Macro) => void; disabled?: boolean }) {
  const [key, setKey] = useState(HID_KEYS[0].hid);
  const [button, setButton] = useState(1);
  const events = macro.events;
  const setEvents = (ev: MacroEvent[]) => onChange({ ...macro, events: ev });
  const move = (i: number, d: -1 | 1) => {
    const ev = [...events];
    [ev[i], ev[i + d]] = [ev[i + d], ev[i]];
    setEvents(ev);
  };
  const setDelay = (i: number, v: number) =>
    setEvents(events.map((e, j) => (j === i ? { ...e, delay_ms: Math.min(DELAY_MAX, Math.max(0, Math.round(v) || 0)) } : e)));
  const cableOnly = events.some((e) => e.kind === "key" && e.code > NKRO_MAX);

  return (
    <div className="flex flex-col gap-3">
      <input type="text" aria-label="Macro name" placeholder="Macro name" maxLength={NAME_MAX} value={macro.name} disabled={disabled}
        onChange={(e) => onChange({ ...macro, name: e.target.value.slice(0, NAME_MAX) })} className={field} />
      {events.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line px-3 py-4 text-center text-[13px] text-muted">
          No events yet. Record, or add key taps and clicks below.</p>
      ) : (
        <ol aria-label="Events" className="no-scrollbar max-h-72 overflow-y-auto rounded-lg border border-line">
          {events.map((e, i) => {
            const label = eventLabel(e);
            return (
              <li key={i} className="flex items-center gap-2 border-b border-line px-2.5 py-1 text-[13px] last:border-b-0">
                <span className="w-6 text-right text-[11px] text-muted" aria-hidden="true">{i + 1}</span>
                <span className="flex-1 truncate">{label}</span>
                <label className="flex items-center gap-1 text-[11px] text-muted">
                  <input type="number" aria-label={`Delay before ${label}`} min={0} max={DELAY_MAX} value={e.delay_ms} disabled={disabled}
                    onChange={(ev) => setDelay(i, Number(ev.target.value))}
                    className="w-20 rounded-md border border-line bg-surface-2 px-1.5 py-0.5 text-right text-[12px] text-ink" />ms
                </label>
                <button type="button" aria-label={`Move ${label} up`} disabled={disabled || i === 0} onClick={() => move(i, -1)} className={icon}>
                  <ArrowUp aria-hidden="true" className="size-3.5" /></button>
                <button type="button" aria-label={`Move ${label} down`} disabled={disabled || i === events.length - 1} onClick={() => move(i, 1)} className={icon}>
                  <ArrowDown aria-hidden="true" className="size-3.5" /></button>
                <button type="button" aria-label={`Remove ${label}`} disabled={disabled} onClick={() => setEvents(events.filter((_, j) => j !== i))} className={icon}>
                  <X aria-hidden="true" className="size-3.5" /></button>
              </li>
            );
          })}
        </ol>
      )}
      <div className="grid grid-cols-[1fr_auto] gap-2">
        <select aria-label="Key to add" value={key} disabled={disabled} onChange={(e) => setKey(Number(e.target.value))} className={field}>
          {GROUPS.map((g) => (
            <optgroup key={g} label={g}>
              {HID_KEYS.filter((k) => k.group === g).map((k) => <option key={k.hid} value={k.hid}>{k.name}</option>)}
            </optgroup>
          ))}
        </select>
        <button type="button" disabled={disabled} onClick={() => setEvents([...events, ...tap(key)])}
          className="rounded-lg border border-line px-3 py-1.5 text-[13px] disabled:opacity-40">Add key tap</button>
        <select aria-label="Mouse button to add" value={button} disabled={disabled} onChange={(e) => setButton(Number(e.target.value))} className={field}>
          {MOUSE_BUTTONS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
        </select>
        <button type="button" disabled={disabled} onClick={() => setEvents([...events, ...click(button)])}
          className="rounded-lg border border-line px-3 py-1.5 text-[13px] disabled:opacity-40">Add mouse click</button>
      </div>
      <p className="text-[12px] text-muted">{events.length} events, plays in about {fmt(totalMs(macro))}
        {cableOnly && <span className="block text-accent">Keys above F21 work over 2.4G only (not over the cable)</span>}</p>
    </div>
  );
}
