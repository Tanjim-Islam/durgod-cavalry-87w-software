import type { ReactNode } from "react";

export function Card({ title, children, className = "" }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-3.5 ${className}`}>
      {title && <h3 className="mb-2 text-xs font-medium text-muted">{title}</h3>}
      {children}
    </section>
  );
}
