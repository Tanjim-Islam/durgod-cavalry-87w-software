import type { KbState } from "@/bridge/types";

export function pillText(s: KbState | null): string {
  if (!s || !s.link) return "Not connected";
  if (s.partial) return "Connect the cable once";
  const kind = s.link === "wired" ? "Wired" : "2.4G";
  if (s.asleep) return `${kind} · keyboard asleep`;
  return s.connected ? `${kind} · connected` : `${kind} · connecting…`;
}

export function ConnectionPill({ state }: { state: KbState | null }) {
  const ok = Boolean(state?.connected && !state.asleep);
  return (
    <span role="status" className="inline-flex items-center gap-2 rounded-full border border-line px-2.5 py-1 text-[11px] text-muted">
      <span aria-hidden="true" className={`size-1.5 rounded-full ${ok ? "bg-accent shadow-[0_0_8px_var(--accent)]" : "bg-muted"}`} />
      {pillText(state)}
    </span>
  );
}
