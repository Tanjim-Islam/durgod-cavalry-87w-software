import { useEffect, useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { Toaster } from "@/components/ui/sonner";
import { Keyboard as KbIcon, Command, Lightbulb, Layers, Settings as Cog, Wand2 } from "lucide-react";
import { useApp, connectEvents } from "@/state/app";
import { ConnectionPill } from "@/components/ConnectionPill";
import { TitleBar } from "@/components/TitleBar";
import { Keyboard } from "@/components/Keyboard";
import { PageShell } from "@/components/PageShell";
import { StatusScreen } from "@/components/StatusScreen";
import { blocked, deviceStatus } from "@/lib/status";
import { Lighting } from "@/pages/Lighting";
import { Keys } from "@/pages/Keys";
import { Macros } from "@/pages/Macros";
import { Shortcuts } from "@/pages/Shortcuts";
import { Profiles } from "@/pages/Profiles";
import { Settings } from "@/pages/Settings";
import { Flyout } from "@/pages/Flyout";

const PAGES = [
  { id: "lighting", label: "Lighting", icon: Lightbulb },
  { id: "keys", label: "Keys", icon: KbIcon },
  { id: "macros", label: "Macros", icon: Wand2 },
  { id: "shortcuts", label: "Shortcuts", icon: Command },
  { id: "profiles", label: "Profiles", icon: Layers },
  { id: "settings", label: "Settings", icon: Cog },
] as const;
type PageId = (typeof PAGES)[number]["id"];
// These pages only make sense with a keyboard to talk to; Profiles and Settings still work offline.
const DEVICE_PAGES = new Set<PageId>(["lighting", "keys", "macros", "shortcuts"]);

export default function App() {
  const { state, refresh, loadSettings } = useApp();
  const themeMode = useApp((s) => s.themeMode);
  const [page, setPage] = useState<PageId>("lighting");
  const status = deviceStatus(state);
  const [route, setRoute] = useState(location.hash);
  useEffect(() => {
    const load = () => { void refresh(); void loadSettings(); };
    connectEvents(); load();
    const h = () => setRoute(location.hash);
    addEventListener("hashchange", h);
    addEventListener("pywebviewready", load);
    return () => { removeEventListener("hashchange", h); removeEventListener("pywebviewready", load); };
  }, [refresh, loadSettings]);

  if (route === "#/flyout") return <MotionConfig reducedMotion="user"><Flyout /><Toaster theme={themeMode} position="top-center" /></MotionConfig>;

  return (
    <MotionConfig reducedMotion="user">
      <div className="grid h-full grid-cols-[176px_1fr] grid-rows-[auto_1fr]">
        <TitleBar />
        <aside className="flex min-h-0 flex-col border-r border-line bg-sidebar px-2.5 pb-4 pt-3">
          <nav aria-label="Pages" className="flex flex-col gap-0.5">
            {PAGES.map((p) => {
              const soon = "soon" in p;
              return (
                <button key={p.id} type="button" disabled={soon} onClick={() => setPage(p.id)}
                  aria-label={soon ? `${p.label} (coming soon)` : p.label}
                  aria-current={page === p.id ? "page" : undefined}
                  className={`relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] transition-colors
                    ${page === p.id ? "text-ink" : "text-muted hover:text-ink"} disabled:opacity-40 disabled:hover:text-muted`}>
                  {page === p.id && <motion.span layoutId="nav" className="absolute inset-0 rounded-lg bg-surface"
                    transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
                  <p.icon aria-hidden="true" className="relative size-4" /><span className="relative">{p.label}</span>
                  {soon && <span aria-hidden="true" className="relative ml-auto text-[10px]">Soon</span>}
                </button>
              );
            })}
          </nav>
          <div className="mt-auto px-1"><ConnectionPill state={state} /></div>
        </aside>
        <main className="relative min-h-0 overflow-hidden">
          <AnimatePresence mode="wait">
            {blocked(status) && DEVICE_PAGES.has(page) ? (
              <PageShell key={`status-${page}`} title={PAGES.find((p) => p.id === page)!.label}
                keyboard={<div className="opacity-40"><Keyboard lighting={null} /></div>}>
                <StatusScreen status={status} />
              </PageShell>
            ) : <>
            {page === "lighting" && <Lighting key="l" />}
            {page === "keys" && <Keys key="k" />}
            {page === "macros" && <Macros key="m" />}
            {page === "shortcuts" && <Shortcuts key="s" />}
            {page === "profiles" && <Profiles key="p" />}
            {page === "settings" && <Settings key="t" />}
            </>}
          </AnimatePresence>
        </main>
      </div>
      <Toaster theme={themeMode} position="bottom-right" />
    </MotionConfig>
  );
}
