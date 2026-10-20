import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Download, RotateCcw, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card } from "@/components/Card";
import { PageShell } from "@/components/PageShell";
import { StateKeyboard } from "@/components/StateKeyboard";
import { call } from "@/bridge/api";
import { useApp } from "@/state/app";

type Confirm = { title: string; body: string; label: string; run: () => Promise<unknown> };

export function Profiles() {
  const { state, profiles, backups, loadProfiles, loadBackups, act } = useApp();
  const off = !state?.connected || state.partial;
  const [name, setName] = useState("");
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => { void loadProfiles(); void loadBackups(); }, [loadProfiles, loadBackups]);

  const ask = (c: Confirm) => { setConfirm(c); setOpen(true); };
  const doSave = async (n: string) => {
    if (await act("save_profile", n)) { setName(""); await loadProfiles(); toast("Profile saved"); }
  };
  const save = () => {
    const n = name.trim();
    if (profiles.some((p) => p.toLowerCase() === n.toLowerCase())) {
      ask({ title: `Overwrite ${n}?`, body: "A profile with this name exists. It is replaced with the current keyboard setup.",
        label: "Overwrite", run: () => doSave(n) });
    } else void doSave(n);
  };
  const exportP = async (p: string) => {
    try { const path = await call<string | null>("export_profile_dialog", p); if (path) toast(`Exported to ${path}`); }
    catch (e) { toast.error((e as Error).message); }
  };
  const importP = async (overwrite = false) => {
    try {
      const n = await call<string | null>("import_profile_dialog", overwrite);
      if (n) { toast(`Imported ${n}`); await loadProfiles(); }
    } catch (e) {
      const msg = (e as Error).message;
      const clash = overwrite ? null : /a profile named (['"])(.+)\1 already exists/.exec(msg);
      if (clash) ask({ title: `Replace existing profile ${clash[2]}?`, label: "Replace", run: () => importP(true),
        body: "The saved profile with this name is replaced by the imported file. Your keyboard is not changed." });
      else toast.error(msg);
    }
  };
  const confirmed = async () => {
    setOpen(false);
    await confirm?.run();
    await loadBackups();
  };

  return (
    <PageShell title="Profiles" meta="Saved setups and automatic backups" keyboard={<StateKeyboard />}>
      <Card title="Profiles">
        <div className="mb-3 flex gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Profile name" aria-label="Profile name" maxLength={40}
            className="flex-1 rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-[13px] outline-none focus:border-accent" />
          <button type="button" disabled={!name.trim()} onClick={save}
            className="rounded-lg bg-accent px-3 py-1.5 text-[13px] font-medium text-on-accent disabled:opacity-40">Save current</button>
          <button type="button" onClick={() => void importP()} className="rounded-lg border border-line px-3 py-1.5 text-[13px]">
            <Upload aria-hidden="true" className="mr-1 inline size-3.5" />Import</button>
        </div>
        <ul className="divide-y divide-line">
          <AnimatePresence initial={false}>
            {profiles.map((p) => (
              <motion.li key={p} layout initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }} className="flex items-center justify-between py-2 text-[13px]">
                <span>{p}</span>
                <span className="flex gap-1.5">
                  <button type="button" aria-label={`Apply ${p}`} disabled={off}
                    onClick={() => ask({ title: `Apply ${p}?`, body: "This writes the profile to your keyboard. A backup is taken first.", label: "Apply", run: () => act("apply_profile", p) })}
                    className="rounded-md bg-surface-2 px-2.5 py-1 disabled:opacity-40">Apply</button>
                  <button type="button" aria-label={`Export ${p}`} onClick={() => exportP(p)} className="rounded-md px-2 py-1 text-muted hover:text-ink"><Download aria-hidden="true" className="size-3.5" /></button>
                  <button type="button" aria-label={`Delete ${p}`}
                    onClick={() => ask({ title: `Delete ${p}?`, body: "The profile file is removed. Your keyboard is not changed.", label: "Delete", run: async () => { await act("delete_profile", p); await loadProfiles(); } })}
                    className="rounded-md px-2 py-1 text-muted hover:text-ink"><Trash2 aria-hidden="true" className="size-3.5" /></button>
                </span>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      </Card>
      <Card title="Backups">
        <ul className="divide-y divide-line">
          {backups.map((b) => (
            <li key={b.name} className="flex items-center justify-between py-2 text-[13px]">
              <span id={`backup-${b.name}`}>
                {b.factory ? <span className="mr-2 rounded bg-accent/15 px-1.5 py-0.5 text-[11px] text-accent">Factory</span> : null}
                {new Date(b.created).toLocaleString()} <span className="text-muted">· {b.label}</span>
              </span>
              <button type="button" aria-describedby={`backup-${b.name}`} disabled={off}
                onClick={() => ask({ title: "Restore this backup to the keyboard?", body: "Your current setup is backed up first.", label: "Restore to keyboard", run: () => act("restore_backup", b.name) })}
                className="rounded-md bg-surface-2 px-2.5 py-1 disabled:opacity-40"><RotateCcw aria-hidden="true" className="mr-1 inline size-3.5" />Restore</button>
            </li>
          ))}
        </ul>
      </Card>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="border-line bg-surface">
          <DialogHeader><DialogTitle className="font-display">{confirm?.title}</DialogTitle>
            <DialogDescription className="text-muted">{confirm?.body}</DialogDescription></DialogHeader>
          <DialogFooter>
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-line px-3 py-1.5 text-[13px]">Cancel</button>
            <button type="button" onClick={confirmed}
              className="rounded-lg bg-accent px-3 py-1.5 text-[13px] font-medium text-on-accent">{confirm?.label}</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
