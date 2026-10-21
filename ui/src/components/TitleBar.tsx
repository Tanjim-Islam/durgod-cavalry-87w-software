import { useEffect, useState, type ReactNode } from "react";
import { Copy, Minus, Square, X } from "lucide-react";
import { onEvent, windowAction } from "@/bridge/api";

function CaptionButton({ label, danger, onClick, children }: { label: string; danger?: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick}
      className={`app-no-drag grid h-full w-11.5 place-items-center text-muted transition-colors duration-150 hover:text-ink
        ${danger ? "hover:bg-destructive hover:text-white" : "hover:bg-surface"}`}>
      {children}
    </button>
  );
}

// Replaces the Windows title bar: the whole strip drags, double-click maximizes, buttons on the right.
export function TitleBar() {
  const [max, setMax] = useState(false);
  useEffect(() => onEvent((e) => { if (e.name === "window") setMax(Boolean(e.payload.maximized)); }), []);
  return (
    <header className="app-drag col-span-2 grid h-9 select-none grid-cols-[176px_1fr]">
      <div className="flex items-center gap-2 border-r border-line bg-sidebar px-4.5 font-display text-[13px] font-semibold tracking-wide">
        <span aria-hidden="true" className="size-2 rounded-full bg-accent shadow-[0_0_10px_var(--accent)]" />Cavalry 87W
      </div>
      <div className="flex justify-end">
        <CaptionButton label="Minimize" onClick={() => void windowAction("minimize")}>
          <Minus aria-hidden="true" className="size-3.5" strokeWidth={1.75} />
        </CaptionButton>
        <CaptionButton label={max ? "Restore" : "Maximize"} onClick={() => void windowAction("toggle_maximize")}>
          {max ? <Copy aria-hidden="true" className="size-3 -scale-x-100" strokeWidth={1.75} />
            : <Square aria-hidden="true" className="size-3" strokeWidth={1.75} />}
        </CaptionButton>
        <CaptionButton label="Close to tray" danger onClick={() => void windowAction("hide_main")}>
          <X aria-hidden="true" className="size-3.5" strokeWidth={1.75} />
        </CaptionButton>
      </div>
    </header>
  );
}
