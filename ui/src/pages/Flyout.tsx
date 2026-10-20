import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Power, RotateCcw, SquareArrowOutUpRight } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ConnectionPill } from "@/components/ConnectionPill";
import { EffectRow } from "@/components/EffectRow";
import { LevelSlider } from "@/components/LevelSlider";
import { windowAction } from "@/bridge/api";
import { useApp } from "@/state/app";

export function Flyout() {
  const { state, act, profiles, backups, settings, loadProfiles, loadBackups, loadSettings, setAppSettings } = useApp();
  const [confirmOpen, setConfirmOpen] = useState(false);
  // The window is hidden and re-shown rather than remounted, so reload whenever it comes back.
  useEffect(() => {
    const reload = () => { void loadProfiles(); void loadBackups(); void loadSettings(); };
    const onVisible = () => { if (document.visibilityState === "visible") reload(); };
    reload();
    addEventListener("focus", reload);
    document.addEventListener("visibilitychange", onVisible);
    return () => { removeEventListener("focus", reload); document.removeEventListener("visibilitychange", onVisible); };
  }, [loadProfiles, loadBackups, loadSettings]);
  useEffect(() => {
    const hide = () => void windowAction("hide_flyout");
    // While the confirm dialog is open, Esc only closes the dialog.
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape" && !confirmOpen) hide(); };
    addEventListener("blur", hide);
    addEventListener("keydown", esc);
    return () => { removeEventListener("blur", hide); removeEventListener("keydown", esc); };
  }, [confirmOpen]);
  const l = state?.lighting;
  const off = !state?.connected || state.partial;
  const newest = backups.find((b) => !b.factory) ?? backups[0];
  const restore = async () => {
    setConfirmOpen(false);
    if (newest) { await act("restore_backup", newest.name); await loadBackups(); }
  };
  return (
    <motion.div className="flex h-full flex-col gap-3 rounded-2xl border border-line bg-bg p-4"
      initial={{ opacity: 0, y: 12, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.18 }}>
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 font-display text-sm font-semibold"><span aria-hidden="true" className="size-2 rounded-full bg-accent shadow-[0_0_10px_var(--accent)]" />Cavalry 87W</span>
        <ConnectionPill state={state} />
      </div>
      <EffectRow effects={state?.effects ?? []} value={l?.effect} disabled={off}
        onChange={(id) => void act("set_lighting", id, null, null, null, null)} />
      <div className="rounded-xl border border-line bg-surface p-3">
        <LevelSlider label="Brightness" value={l?.brightness} max={4} disabled={off} onCommit={(v) => act("set_lighting", null, v, null, null, null)} />
      </div>
      <label className="flex items-center justify-between rounded-xl border border-line bg-surface p-3 text-[13px]">Keep lights on
        <Switch aria-label="Keep lights on" checked={Boolean(l?.keep_lights_on)} disabled={off} onCheckedChange={(v) => void act("set_keep_lights_on", v)} />
      </label>
      <select aria-label="Profile" disabled={off || profiles.length === 0} value=""
        onChange={async (e) => { const p = e.target.value; if (p) { await act("apply_profile", p); await loadBackups(); } }}
        className="rounded-lg border border-line bg-surface-2 px-2 py-1.5 text-[13px]">
        <option value="" disabled>Apply a profile…</option>
        {profiles.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      <div className="mt-auto flex items-center justify-between border-t border-line pt-3 text-[12px]">
        <label className="flex items-center gap-2 text-muted">
          <Switch aria-label="Start with Windows" checked={settings.autostart} onCheckedChange={(v) => void setAppSettings({ autostart: v })} />Start with Windows
        </label>
        <span className="flex gap-1">
          <button type="button" aria-label="Restore" title="Restore newest backup" disabled={!newest || off}
            onClick={() => setConfirmOpen(true)} className="rounded-md p-1.5 text-muted hover:text-ink disabled:opacity-40"><RotateCcw aria-hidden="true" className="size-4" /></button>
          <button type="button" aria-label="Quit" onClick={() => void windowAction("quit")} className="rounded-md p-1.5 text-muted hover:text-ink"><Power aria-hidden="true" className="size-4" /></button>
          <button type="button" onClick={() => void windowAction("show_main")} className="flex items-center gap-1 rounded-md bg-accent px-2.5 py-1.5 font-medium text-on-accent">
            Open app<SquareArrowOutUpRight aria-hidden="true" className="size-3.5" /></button>
        </span>
      </div>
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="border-line bg-surface" showCloseButton={false}>
          <DialogHeader><DialogTitle className="font-display">Restore this backup to the keyboard?</DialogTitle>
            <DialogDescription className="text-muted">
              {newest ? `${new Date(newest.created).toLocaleString()} · ${newest.label}. ` : ""}Your current setup is backed up first.
            </DialogDescription></DialogHeader>
          <DialogFooter>
            <button type="button" onClick={() => setConfirmOpen(false)} className="rounded-lg border border-line px-3 py-1.5 text-[13px]">Cancel</button>
            <button type="button" onClick={restore} className="rounded-lg bg-accent px-3 py-1.5 text-[13px] font-medium text-on-accent">Restore to keyboard</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
