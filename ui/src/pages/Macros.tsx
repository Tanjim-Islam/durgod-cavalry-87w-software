import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { call } from "@/bridge/api";
import type { Macro, MacroEvent } from "@/bridge/types";
import { AssignDialog } from "@/components/AssignDialog";
import { Card } from "@/components/Card";
import { MacroEditor } from "@/components/MacroEditor";
import { PageShell } from "@/components/PageShell";
import { StateKeyboard } from "@/components/StateKeyboard";
import { NEEDS_CABLE } from "@/lib/copy";
import { MACRO_LIMIT, macroBytes } from "@/lib/macro";
import { useApp } from "@/state/app";

type Sel = number | "new" | null;
const btn = "rounded-lg border border-line px-3 py-1.5 text-[13px] disabled:opacity-40";
const quietStop = () => void call("record_macro_stop").catch((e) => console.warn("Couldn't stop the macro recorder", e));
const fade = { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -6 } };

export function Macros() {
  const { state, run, act, refresh } = useApp();
  const [sel, setSel] = useState<Sel>(null);
  const [draft, setDraft] = useState<Macro | null>(null);
  const [recording, setRecording] = useState(false);
  const [assign, setAssign] = useState(false);
  const [confirm, setConfirm] = useState<"delete" | "clear" | null>(null);
  const [session, setSession] = useState(0); // bumps per opened macro, so saving keeps the editor in place
  const [recBusy, setRecBusy] = useState(false);
  // A start was sent and no stop yet; a start is still in flight; the page is mounted.
  const active = useRef(false);
  const starting = useRef(false);
  const mounted = useRef(true);
  const macros = state?.macros ?? null;
  const off = !state?.connected || state.partial || !macros;

  // Stop an active recording when leaving the page; a pending start stops itself when it lands.
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (active.current && !starting.current) { active.current = false; quietStop(); }
    };
  }, []);
  // Drop the selection if its macro went away (adjusting state during render).
  if (typeof sel === "number" && (!macros || sel >= macros.length)) { setSel(null); setDraft(null); }

  const open = (s: Sel) => {
    setSel(s);
    setSession((n) => n + 1);
    setDraft(s === "new" ? { name: "", events: [] } : s == null || !macros ? null : structuredClone(macros[s]));
  };
  const all = macros ? (draft ? (sel === "new" ? [...macros, draft] : macros.map((m, i) => (i === sel ? draft : m))) : macros) : [];
  const used = macroBytes(all);
  const over = used > MACRO_LIMIT;
  const canSave = !!draft && !off && !recording && !over && draft.name.trim() !== "" && draft.events.length > 0;

  const startRecord = async () => {
    active.current = true; starting.current = true; setRecBusy(true);
    const ok = await act("record_macro_start");
    starting.current = false;
    if (!ok) active.current = false;
    if (!mounted.current) { if (ok) { active.current = false; quietStop(); } return; }
    setRecBusy(false);
    if (ok) setRecording(true);
  };
  const stopRecord = async () => {
    if (!active.current) return;
    active.current = false; setRecBusy(true);
    const r = await run<{ events: MacroEvent[]; truncated: boolean }>("record_macro_stop");
    setRecBusy(false); setRecording(false);
    if (!r) return;
    setDraft((d) => (d ? { ...d, events: r.events } : d));
    if (r.truncated) toast("Recording was cut off at the size limit");
  };
  // The draft went away mid-recording (e.g. the keyboard disconnected): stop and drop the events.
  const orphaned = recording && !recBusy && !draft;
  useEffect(() => {
    if (!orphaned || !active.current) return;
    active.current = false;
    void run("record_macro_stop").then(() => setRecording(false));
  }, [orphaned, run]);
  const save = async () => {
    if (!draft) return;
    const r = await run<{ index: number }>("save_macro", typeof sel === "number" ? sel : null, draft);
    if (!r) return;
    await refresh();
    setSel(r.index);
  };
  const remove = async () => {
    setConfirm(null);
    if (typeof sel === "number" && (await act("delete_macro", sel))) open(null);
  };
  const clearAll = async () => {
    setConfirm(null);
    if (await act("clear_macros")) open(null);
  };

  return (
    <PageShell title="Macros" meta="Recorded on this PC, stored on your keyboard" keyboard={<StateKeyboard />}>
      <AnimatePresence initial={false}>
        {recording && (
          <motion.div key="rec" {...fade} role="status"
            className="flex items-center gap-3 rounded-xl border border-destructive/50 bg-surface px-3.5 py-2.5 text-[13px]">
            <motion.span aria-hidden="true" className="size-2 rounded-full bg-destructive"
              animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.2, repeat: Infinity }} />
            <span className="flex-1">Recording. Type the keys you want, then stop.</span>
            <button type="button" disabled={recBusy} onClick={() => void stopRecord()}
              className={`${btn} border-destructive text-destructive`}>Stop recording</button>
          </motion.div>
        )}
      </AnimatePresence>
      {!state?.connected ? (
        <Card><p className="text-[13px] text-muted">Connect the keyboard to edit macros.</p></Card>
      ) : state.partial ? (
        <Card><p className="text-[13px] text-muted">{NEEDS_CABLE}.</p></Card>
      ) : !macros ? (
        <Card title="Macros couldn't be read">
          <p className="mb-3 text-[13px]">{state.macros_error || "The macro memory on the keyboard couldn't be read."}</p>
          {state.macros_error && <button type="button" disabled={recording} onClick={() => setConfirm("clear")} className={btn}>Clear all macros</button>}
        </Card>
      ) : (
        <div className="grid items-start gap-4 md:grid-cols-[200px_minmax(0,1fr)]">
          <Card title="Your macros" className="flex flex-col gap-3">
            <ul className="flex flex-col gap-0.5">
              <AnimatePresence initial={false}>
                {macros.map((m, i) => (
                  <motion.li key={`${i}-${m.name}`} layout {...fade}>
                    <button type="button" aria-label={`Macro ${i + 1}: ${m.name}`} aria-pressed={sel === i} disabled={recording}
                      onClick={() => open(i)}
                      className={`w-full truncate rounded-md px-2.5 py-1.5 text-left text-[13px] disabled:opacity-50 ${sel === i ? "bg-accent text-on-accent" : "hover:bg-surface-2"}`}>
                      <span aria-hidden="true" className="mr-1.5 opacity-60">{i + 1}.</span>{m.name}
                    </button>
                  </motion.li>
                ))}
              </AnimatePresence>
              {macros.length === 0 && <li className="px-2.5 py-1.5 text-[12px] text-muted">No macros yet</li>}
            </ul>
            <button type="button" disabled={recording} onClick={() => open("new")}
              className={`${btn} mt-2 flex items-center justify-center gap-1.5`}><Plus aria-hidden="true" className="size-3.5" />New macro</button>
            <div className="mt-2">
              <div role="meter" aria-label="Macro storage" aria-valuemin={0} aria-valuemax={MACRO_LIMIT} aria-valuenow={used}
                aria-valuetext={`${used} of ${MACRO_LIMIT} bytes`} className="h-1.5 overflow-hidden rounded-full bg-surface-2">
                <motion.div className={`h-full rounded-full ${over ? "bg-destructive" : "bg-accent"}`}
                  animate={{ width: `${Math.min(100, (used / MACRO_LIMIT) * 100)}%` }} transition={{ duration: 0.25 }} />
              </div>
              <p className={`mt-1 text-[11px] ${over ? "text-destructive" : "text-muted"}`}>
                {over ? `Too big: ${used} of ${MACRO_LIMIT} bytes` : `${used} of ${MACRO_LIMIT} bytes used`}</p>
            </div>
          </Card>
          <AnimatePresence mode="popLayout" initial={false}>
            {draft ? (
              <motion.div key={session} {...fade}>
                <Card title={sel === "new" ? "New macro" : `Macro ${Number(sel) + 1}`}>
                  <MacroEditor macro={draft} onChange={setDraft} disabled={recording} />
                  <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
                    <button type="button" disabled={recording || recBusy || off} onClick={() => void startRecord()} className={btn}>Record</button>
                    <button type="button" disabled={typeof sel !== "number" || recording} onClick={() => setAssign(true)} className={btn}>Assign to key</button>
                    <button type="button" disabled={typeof sel !== "number" || recording} onClick={() => setConfirm("delete")} className={btn}>Delete</button>
                    <button type="button" disabled={!canSave} onClick={() => void save()}
                      className="ml-auto rounded-lg bg-accent px-3 py-1.5 text-[13px] font-medium text-on-accent disabled:opacity-40">Save</button>
                  </div>
                </Card>
              </motion.div>
            ) : (
              <motion.div key="empty" {...fade}>
                <Card><p className="text-[13px] text-muted">Pick a macro or make a new one.</p></Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
      {typeof sel === "number" && <AssignDialog open={assign} macroIndex={sel} onClose={() => setAssign(false)} />}
      <Dialog open={confirm != null} onOpenChange={(o) => { if (!o) setConfirm(null); }}>
        <DialogContent className="border-line bg-surface">
          <DialogHeader>
            <DialogTitle className="font-display">{confirm === "clear" ? "Clear all macros?" : `Delete ${(typeof sel === "number" && macros?.[sel]?.name) || "this macro"}?`}</DialogTitle>
            <DialogDescription className="text-muted">{confirm === "clear"
              ? "Every macro is erased and keys that played one are unbound. A backup is taken first."
              : "Keys that play this macro are unbound, and later macros move up one number. A backup is taken first."}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button type="button" onClick={() => setConfirm(null)} className={btn}>Cancel</button>
            <button type="button" onClick={() => void (confirm === "clear" ? clearAll() : remove())}
              className="rounded-lg bg-accent px-3 py-1.5 text-[13px] font-medium text-on-accent">{confirm === "clear" ? "Clear all" : "Delete"}</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
