import { AnimatePresence, motion } from "motion/react";
import { ArrowDownToLine, CircleCheck, LoaderCircle, RotateCw, Sparkles } from "lucide-react";
import { useUpdate, type UpdateState } from "@/state/update";

const pct = (u: UpdateState) => `${Math.round(u.progress * 100)}%`;

// Bottom of the sidebar: what the launch-time update check found, and the download/install progress.
export function UpdateBox() {
  const { update: u, check, install } = useUpdate();
  if (!u || u.status === "idle") return null;
  const busy = u.status === "downloading" || u.status === "installing";
  return (
    <AnimatePresence mode="wait">
      <motion.div key={u.status} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.18 }} role="status" aria-label="Updates">
        {u.status === "checking" && (
          <p className="flex items-center gap-1.5 px-1 text-[11px] text-muted">
            <LoaderCircle aria-hidden="true" className="size-3 animate-spin" />Checking for updates…
          </p>
        )}
        {u.status === "current" && (
          <p className="flex items-center gap-1.5 px-1 text-[11px] text-muted">
            <CircleCheck aria-hidden="true" className="size-3" />Up to date · v{u.current}
          </p>
        )}
        {u.status === "error" && (
          <button type="button" onClick={() => void check()} className="flex items-center gap-1.5 px-1 text-left text-[11px] text-muted hover:text-ink">
            <RotateCw aria-hidden="true" className="size-3 shrink-0" />Couldn't check for updates. Retry
          </button>
        )}
        {(u.status === "available" || busy) && (
          <div className="flex flex-col gap-2 rounded-lg border border-accent/40 bg-surface p-2.5">
            <p className="flex items-center gap-1.5 text-[12px] font-medium">
              <Sparkles aria-hidden="true" className="size-3.5 text-accent" />
              {u.status === "available" ? "Update available" : u.status === "downloading" ? "Downloading update" : "Installing update"}
            </p>
            <p className="text-[11px] text-muted">
              {u.status === "installing" ? "Cavalry will close and reopen in a moment." : `v${u.current} → v${u.latest}`}
            </p>
            {u.status === "downloading" && (
              <div className="h-1 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-label="Download progress"
                aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(u.progress * 100)}>
                <motion.div className="h-full bg-accent" animate={{ width: pct(u) }} transition={{ duration: 0.2 }} />
              </div>
            )}
            {u.status === "installing" && <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin text-muted" />}
            {u.error && <p className="text-[11px] text-accent">{u.error}</p>}
            {u.status === "available" && (
              <div className="flex items-center justify-between gap-2">
                <button type="button" onClick={() => void install()}
                  className="flex items-center gap-1 rounded-md bg-accent px-2 py-1 text-[11px] font-medium text-on-accent">
                  <ArrowDownToLine aria-hidden="true" className="size-3" />{u.installable ? "Install" : "Download"}
                </button>
                {u.url && <a href={u.url} target="_blank" rel="noreferrer" className="whitespace-nowrap text-[11px] text-muted underline-offset-2 hover:text-ink hover:underline">What's new</a>}
              </div>
            )}
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}

// Settings: the version, what the last check said, and a button to check again.
export function UpdateSettings() {
  const { update: u, check, install } = useUpdate();
  const busy = !u || u.status === "checking" || u.status === "downloading" || u.status === "installing";
  const line = !u ? "Updates aren't available here." : {
    idle: "Not checked yet.", checking: "Checking for updates…", current: "You're on the latest version.",
    available: `Version ${u.latest} is available.`, downloading: `Downloading version ${u.latest}… ${pct(u)}`,
    installing: "Installing. Cavalry will close and reopen.", error: u.error ?? "Couldn't check for updates.",
  }[u.status];
  return (
    <div className="flex flex-col gap-3 text-[13px]">
      <p className="flex items-baseline justify-between">Version<span className="font-medium">{u ? `v${u.current}` : "Unknown"}</span></p>
      <p className="text-muted" aria-live="polite">{line}</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" disabled={busy} onClick={() => void check()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 hover:bg-surface-2 disabled:opacity-40">
          <RotateCw aria-hidden="true" className={`size-3.5 ${u?.status === "checking" ? "animate-spin" : ""}`} />Check for updates
        </button>
        {u?.status === "available" && (
          <button type="button" onClick={() => void install()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 font-medium text-on-accent">
            <ArrowDownToLine aria-hidden="true" className="size-3.5" />{u.installable ? `Install v${u.latest}` : "Download"}
          </button>
        )}
      </div>
    </div>
  );
}
