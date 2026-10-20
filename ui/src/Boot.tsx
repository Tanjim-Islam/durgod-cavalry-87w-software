import { useEffect, useState, type ReactNode } from "react";
import { hasApi, inWebView, READY_TIMEOUT_MS } from "@/bridge/api";

type Phase = "starting" | "ready" | "failed";

/** In the desktop app, hold the UI until pywebview's api is in; never fall back to fake data. */
export function Boot({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>(() => (hasApi() || !inWebView() ? "ready" : "starting"));
  useEffect(() => {
    if (hasApi() || !inWebView()) return;
    const onReady = () => { if (hasApi()) setPhase("ready"); };
    const timer = setTimeout(() => setPhase((p) => (p === "ready" ? p : "failed")), READY_TIMEOUT_MS);
    addEventListener("pywebviewready", onReady);
    onReady();
    return () => { clearTimeout(timer); removeEventListener("pywebviewready", onReady); };
  }, []);

  if (phase === "ready") return <>{children}</>;
  return (
    <div className="grid h-full place-items-center p-6 text-center text-[13px] text-muted">
      {phase === "starting" ? <p>Starting…</p>
        : <p role="alert">The app's engine didn't start. Restart Cavalry; if it keeps happening, check the log.</p>}
    </div>
  );
}
