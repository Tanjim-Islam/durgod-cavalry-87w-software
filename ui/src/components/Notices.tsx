import { AnimatePresence, motion } from "motion/react";
import { Info, TriangleAlert, X } from "lucide-react";
import { useApp } from "@/state/app";

const PENDING = "A change is waiting for the keyboard. It's applied as soon as the keyboard reconnects.";

// Non-blocking warnings from the engine, plus a note while a change waits for the keyboard to come back.
export function Notices() {
  const state = useApp((s) => s.state);
  const act = useApp((s) => s.act);
  const items = [
    ...(state?.pending ? [{ code: "pending", message: PENDING, info: true }] : []),
    ...(state?.notices ?? []).map((n) => ({ ...n, info: false })),
  ];
  return (
    <AnimatePresence initial={false}>
      {items.map((n) => (
        <motion.div key={n.code} role={n.info ? "status" : "alert"} className="overflow-hidden"
          initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
          <div className={`flex items-start gap-2.5 rounded-lg border bg-surface px-3 py-2 text-[13px] ${n.info ? "border-line" : "border-accent/40"}`}>
            {n.info ? <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-muted" />
              : <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-accent" />}
            <p className="flex-1">{n.message}</p>
            {!n.info && (
              <button type="button" aria-label="Dismiss" title="Dismiss" onClick={() => void act("dismiss_notice", n.code)}
                className="rounded p-0.5 text-muted hover:text-ink">
                <X aria-hidden="true" className="size-3.5" />
              </button>
            )}
          </div>
        </motion.div>
      ))}
    </AnimatePresence>
  );
}
