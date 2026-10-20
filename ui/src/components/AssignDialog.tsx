import { useMemo, useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Keyboard } from "@/components/Keyboard";
import { Segmented } from "@/components/Segmented";
import { NEEDS_CABLE } from "@/lib/copy";
import { FN_LAYERS, FN_SLOT, KEYS } from "@/lib/layout";
import { clampRepeat } from "@/lib/macro";
import { useApp } from "@/state/app";

const LAYERS: ["0" | "1" | "3", string][] = [["0", "Base"], ["1", "Fn layer"], ["3", "WASD swap"]];

// Binds a saved macro to a key on one of the layers.
export function AssignDialog({ open, macroIndex, onClose }: { open: boolean; macroIndex: number; onClose: () => void }) {
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="border-line bg-surface sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="font-display">Assign macro to a key</DialogTitle>
          <DialogDescription className="text-muted">Pick a layer and a key. The key will play this macro.</DialogDescription>
        </DialogHeader>
        {open && <Body macroIndex={macroIndex} onClose={onClose} />}
      </DialogContent>
    </Dialog>
  );
}

function Body({ macroIndex, onClose }: { macroIndex: number; onClose: () => void }) {
  const { state, act } = useApp();
  const [layerKey, setLayerKey] = useState<"0" | "1" | "3">("0");
  const [slot, setSlot] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [mode, setMode] = useState<"1" | "2" | "4">("1");
  const [count, setCount] = useState("1");
  const [busy, setBusy] = useState(false);
  const layer = Number(layerKey);
  const actions = state?.layers?.[layer];
  // Mark keys on this layer that already play this macro.
  const marks = useMemo(() => new Set(actions ? actions.flatMap((a, s) => (a.type === "macro" && a.index === macroIndex ? [s] : [])) : []),
    [actions, macroIndex]);
  const pick = (s: number) => {
    if (FN_LAYERS.includes(layer) && s === FN_SLOT) { setSlot(null); setNote("The Fn key can't hold a macro. Pick another key."); return; }
    setNote(""); setSlot(s);
  };
  const changeLayer = (v: "0" | "1" | "3") => {
    setLayerKey(v); setNote("");
    if ((v === "0" || v === "3") && slot === FN_SLOT) setSlot(null);
  };
  const off = !state?.connected || state.partial || !actions;
  const name = KEYS.find((k) => k.slot === slot)?.name;
  const assign = async () => {
    if (slot == null) return;
    setBusy(true);
    const ok = await act("remap_key", layer, slot, { type: "macro", index: macroIndex, mode: Number(mode), count: mode === "1" ? clampRepeat(count) : 1 });
    setBusy(false);
    if (ok) onClose();
  };

  return (<>
    <div className="flex flex-col gap-3">
      <Segmented label="Layer" value={layerKey} options={LAYERS} onChange={changeLayer} />
      <div className="no-scrollbar overflow-x-auto">
        <Keyboard unit={28} lighting={state?.lighting} palette={state?.palette} keyColors={state?.key_colors}
          selected={slot} marks={marks} markLabel="plays this macro" onKeyClick={pick} />
      </div>
      <p className="min-h-5 text-[12px] text-muted" aria-live="polite">{note || (state?.connected && state.partial ? NEEDS_CABLE : name ? `Selected: ${name}` : "Click a key")}</p>
      <div className="flex flex-wrap items-center gap-3">
        <Segmented label="Play mode" value={mode} options={[["1", "Once"], ["2", "While held"], ["4", "Toggle"]]} onChange={setMode} />
        {mode === "1" && <label className="flex items-center gap-2 text-[13px]">Repeat
          <input type="number" aria-label="Repeat count" min={1} max={255} value={count}
            onChange={(e) => setCount(e.target.value)} onBlur={() => setCount(String(clampRepeat(count)))}
            className="w-20 rounded-md border border-line bg-surface-2 px-2 py-1 text-right" /></label>}
      </div>
    </div>
    <DialogFooter>
      <button type="button" onClick={onClose} className="rounded-lg border border-line px-3 py-1.5 text-[13px]">Cancel</button>
      <button type="button" disabled={slot == null || off || busy} onClick={() => void assign()}
        className="rounded-lg bg-accent px-3 py-1.5 text-[13px] font-medium text-on-accent disabled:opacity-40">Assign</button>
    </DialogFooter>
  </>);
}
