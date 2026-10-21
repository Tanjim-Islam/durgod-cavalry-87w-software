import type { ComponentType } from "react";
import { motion } from "motion/react";
import { CircleAlert, FolderOpen, KeyboardOff, LoaderCircle, Moon, RotateCw, Unplug, Usb } from "lucide-react";
import { windowAction } from "@/bridge/api";
import type { Blocked } from "@/lib/status";
import { useApp } from "@/state/app";

interface Copy {
  icon: ComponentType<{ className?: string; "aria-hidden"?: boolean }>; title: string; body: string;
  steps?: string[]; retry?: boolean; logs?: boolean; spin?: boolean; warn?: boolean;
}

const COPY: Record<Blocked["kind"], Copy> = {
  starting: { icon: LoaderCircle, spin: true, title: "Looking for your keyboard", body: "One moment." },
  none: {
    icon: Usb, title: "No keyboard found",
    body: "Connect your Cavalry 87W with the cable or the 2.4G dongle.",
    steps: ["Cable: plug it in, then press Fn + PrtSc to switch the keyboard to wired mode. In 2.4G mode the cable only charges.",
      "2.4G: plug the dongle into this PC, then press Fn + ScrLk to switch the keyboard to 2.4G mode.",
      "Make sure the keyboard's power switch is on."],
  },
  connecting: {
    icon: LoaderCircle, spin: true, title: "Connecting to your keyboard",
    body: "The keyboard was just plugged in or switched modes. Give it a few seconds to settle.",
  },
  asleep: {
    icon: Moon, title: "Keyboard isn't answering",
    body: "The 2.4G dongle is plugged in, but the keyboard isn't talking to it.",
    steps: ["Press any key to wake it up.", "If it's in Bluetooth or wired mode, press Fn + ScrLk to switch it to 2.4G.",
      "Check that the power switch is on and the battery isn't empty."],
  },
  wrong_model: {
    icon: KeyboardOff, warn: true, title: "This isn't a Cavalry 87W",
    body: "A device answered, but it's a different model. This app only works with the Durgod Cavalry 87W, so it won't send it anything.",
    steps: ["If you have more than one keyboard or dongle plugged in, unplug the others.",
      "Other keyboards that use the same kind of dongle aren't supported."],
    retry: true,
  },
  connect_failed: {
    icon: CircleAlert, warn: true, title: "Couldn't talk to the keyboard",
    body: "The keyboard is connected, but reading it failed.",
    steps: ["Close Durgod's software or any other app that controls the keyboard.",
      "Unplug the cable or dongle and plug it back in.", "Try a different USB port."],
    retry: true, logs: true,
  },
  lost: {
    icon: Unplug, warn: true, title: "Lost the keyboard",
    body: "The connection dropped. The app keeps trying to reconnect on its own.",
    steps: ["Check the cable or dongle.", "If the keyboard went to sleep, press any key."],
    retry: true, logs: true,
  },
};

const BUTTON = "inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-[13px] hover:bg-surface-2 disabled:opacity-40";

// Shown instead of a keyboard page (and, compact, in the flyout) when there's nothing to talk to.
export function StatusScreen({ status, compact = false }: { status: Blocked; compact?: boolean }) {
  const act = useApp((s) => s.act);
  const busy = useApp((s) => s.busy);
  const c = COPY[status.kind];
  const Icon = c.icon;
  const detail = "detail" in status ? status.detail : null;
  return (
    <motion.section role={c.warn ? "alert" : "status"} aria-label={c.title}
      initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}
      className={`rounded-xl border bg-surface ${c.warn ? "border-accent/40" : "border-line"} ${compact ? "p-3.5" : "p-5"}`}>
      <div className="flex items-start gap-3">
        <span className={`grid shrink-0 place-items-center rounded-lg bg-surface-2 ${compact ? "size-8" : "size-10"} ${c.warn ? "text-accent" : "text-muted"}`}>
          <Icon aria-hidden={true} className={`${compact ? "size-4" : "size-5"} ${c.spin ? "animate-spin" : ""}`} />
        </span>
        <div className="flex min-w-0 flex-col gap-2">
          <h2 className={`font-display font-semibold ${compact ? "text-sm" : "text-base"}`}>{c.title}</h2>
          <p className="text-[13px] text-muted">{c.body}</p>
          {detail && <p className="break-words rounded-md bg-surface-2 px-2.5 py-1.5 font-mono text-[11px] text-muted">{detail}</p>}
          {c.steps && !compact && (
            <ul className="flex list-disc flex-col gap-1 pl-4 text-[13px] text-muted marker:text-accent">
              {c.steps.map((s) => <li key={s}>{s}</li>)}
            </ul>
          )}
          {(c.retry || (c.logs && !compact)) && (
            <div className="flex flex-wrap gap-2">
              {c.retry && (
                <button type="button" className={BUTTON} disabled={busy} onClick={() => void act("retry_connect")}>
                  <RotateCw aria-hidden="true" className="size-3.5" />Try again
                </button>
              )}
              {c.logs && !compact && (
                <button type="button" className={BUTTON} onClick={() => void windowAction("open_logs")}>
                  <FolderOpen aria-hidden="true" className="size-3.5" />Open log folder
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </motion.section>
  );
}
