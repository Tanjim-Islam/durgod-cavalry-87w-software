import { useEffect } from "react";
import { motion } from "motion/react";
import { Card } from "@/components/Card";
import { PageShell } from "@/components/PageShell";
import { useApp } from "@/state/app";

const GROUPS = ["Media", "Lighting", "Connection", "System"];

function Keys({ text }: { text: string }) {
  return (
    <span className="flex items-center gap-1">
      {text.split(" + ").map((k, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <span className="text-muted">+</span>}
          <kbd className="rounded-md border border-line bg-surface-2 px-1.5 py-0.5 font-sans text-[11px] text-ink shadow-[inset_0_-1px_0_rgba(0,0,0,.3)]">{k}</kbd>
        </span>
      ))}
    </span>
  );
}

export function Shortcuts() {
  const { shortcuts, loadShortcuts } = useApp();
  useEffect(() => { void loadShortcuts(); }, [loadShortcuts]);
  return (
    <PageShell title="Shortcuts" meta="Every Fn shortcut, read from your keyboard">
      <div className="grid gap-3 lg:grid-cols-2">
        {GROUPS.map((g) => (
          <Card key={g}>
            <section role="region" aria-label={g}>
              <h3 className="mb-2 font-display text-sm font-semibold">{g}</h3>
              <ul className="divide-y divide-line">
                {(shortcuts ?? []).filter((r) => r.group === g).map((r, i) => (
                  <motion.li key={r.keys} className="flex items-center justify-between gap-3 py-2 text-[13px]"
                    initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.02 }}>
                    <Keys text={r.keys} />
                    <span className="text-right">
                      {r.changed ? r.current : r.label}
                      {r.changed && <span className="block text-[11px] text-muted">Factory: {r.label}</span>}
                    </span>
                  </motion.li>
                ))}
              </ul>
            </section>
          </Card>
        ))}
      </div>
    </PageShell>
  );
}
