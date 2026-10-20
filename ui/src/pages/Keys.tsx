import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ActionEditor } from "@/components/ActionEditor";
import { Card } from "@/components/Card";
import { Keyboard } from "@/components/Keyboard";
import { PageShell } from "@/components/PageShell";
import { Segmented } from "@/components/Segmented";
import { describe, isRemapped } from "@/lib/describe";
import { KEYS } from "@/lib/layout";
import { useApp } from "@/state/app";

const LAYERS: ["0" | "1" | "3", string][] = [["0", "Base"], ["1", "Fn layer"], ["3", "WASD swap"]];

export function Keys() {
  const { state, act } = useApp();
  const [layerKey, setLayerKey] = useState<"0" | "1" | "3">("0");
  const [slot, setSlot] = useState<number | null>(null);
  const [confirm, setConfirm] = useState(false);
  const layer = Number(layerKey);
  const actions = state?.layers?.[layer] ?? null;
  const off = !state?.connected || state.partial || !actions;
  const marks = useMemo(() => new Set(actions ? actions.flatMap((a, s) => (isRemapped(layer, s, a) ? [s] : [])) : []), [actions, layer]);
  const meta = !state?.connected ? "Connect the keyboard to change keys"
    : off ? (state.layers_error || "Couldn't read the key layout. Reconnect the keyboard.")
    : "Click a key to change what it does";
  const cap = KEYS.find((k) => k.slot === slot);
  const current = slot != null && actions ? actions[slot] : null;
  return (
    <PageShell title="Keys" meta={meta}
      keyboard={<Keyboard lighting={state?.lighting} palette={state?.palette} keyColors={state?.key_colors}
        selected={slot} marks={marks} onKeyClick={setSlot} />}>
      <div className="flex items-center justify-between">
        <Segmented label="Layer" value={layerKey} options={LAYERS} onChange={setLayerKey} />
        <button type="button" disabled={off} onClick={() => setConfirm(true)} className="rounded-lg border border-line px-3 py-1.5 text-[13px] disabled:opacity-40">Reset layer</button>
      </div>
      <AnimatePresence mode="wait">
        {cap && current && slot != null && (
          <motion.div key={`${layer}-${slot}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>
            <Card title={cap.name}>
              <p className="mb-3 text-[13px]">Now: {describe(current)}</p>
              {layer === 0 && slot === 59 ? (
                <p className="text-[13px] text-muted">The Fn key can't be remapped. It opens all your Fn shortcuts.</p>
              ) : (<>
                <ActionEditor key={`${layer}-${slot}-${JSON.stringify(current)}`} value={current} macros={state?.macros ?? []} disabled={off}
                  onApply={(a) => void act("remap_key", layer, slot, a)} />
                <button type="button" disabled={off} onClick={() => void act("reset_key", layer, slot)}
                  className="mt-3 text-[12px] text-muted underline-offset-2 hover:text-ink hover:underline disabled:opacity-40">Reset key</button>
              </>)}
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogContent className="border-line bg-surface">
          <DialogHeader><DialogTitle className="font-display">Reset the {LAYERS.find(([v]) => v === layerKey)?.[1]}?</DialogTitle>
            <DialogDescription className="text-muted">Every key on this layer goes back to its factory action. A backup is taken first.</DialogDescription></DialogHeader>
          <DialogFooter>
            <button type="button" onClick={() => setConfirm(false)} className="rounded-lg border border-line px-3 py-1.5 text-[13px]">Cancel</button>
            <button type="button" onClick={() => { setConfirm(false); void act("reset_layer", layer); }} className="rounded-lg bg-accent px-3 py-1.5 text-[13px] font-medium text-on-accent">Reset layer</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
