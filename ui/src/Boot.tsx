import { useEffect, useState, type ReactNode } from "react";
import { LoaderCircle, RotateCw, ServerCrash } from "lucide-react";
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
  if (phase === "starting") {
    return (
      <div className="grid h-full place-items-center bg-bg text-[13px] text-muted">
        <p role="status" className="flex items-center gap-2"><LoaderCircle aria-hidden="true" className="size-4 animate-spin" />Starting…</p>
      </div>
    );
  }
  return (
    <div className="grid h-full place-items-center bg-bg p-6">
      <section role="alert" aria-label="The app's engine didn't start"
        className="flex max-w-md flex-col gap-3 rounded-xl border border-accent/40 bg-surface p-5">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-lg bg-surface-2 text-accent">
            <ServerCrash aria-hidden="true" className="size-5" />
          </span>
          <h1 className="font-display text-base font-semibold">The app's engine didn't start</h1>
        </div>
        <p className="text-[13px] text-muted">
          The window opened, but the part that talks to the keyboard never answered. Try reloading. If it keeps
          happening, quit Cavalry from the tray and open it again.
        </p>
        <p className="rounded-md bg-surface-2 px-2.5 py-1.5 font-mono text-[11px] text-muted">
          Log: %APPDATA%\Cavalry87\logs\app.log
        </p>
        <button type="button" onClick={() => location.reload()}
          className="inline-flex w-fit items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-[13px] font-medium text-on-accent">
          <RotateCw aria-hidden="true" className="size-3.5" />Reload
        </button>
      </section>
    </div>
  );
}
