import type { ReactNode } from "react";
import { motion } from "motion/react";

export function PageShell({ title, meta, keyboard, children }: { title: string; meta?: string; keyboard?: ReactNode; children: ReactNode }) {
  return (
    <motion.div className="flex h-full flex-col gap-4 overflow-y-auto no-scrollbar [&>*]:shrink-0 px-7 py-6"
      initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}>
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight">{title}</h1>
        {meta && <p className="mt-0.5 text-xs text-muted">{meta}</p>}
      </header>
      {keyboard}
      {children}
    </motion.div>
  );
}
