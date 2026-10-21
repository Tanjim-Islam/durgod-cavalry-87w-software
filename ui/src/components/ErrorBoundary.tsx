import { Component, type ErrorInfo, type ReactNode } from "react";
import { Bug, Copy, RotateCw } from "lucide-react";

const BUTTON = "inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-[13px] hover:bg-surface-2";

// Last line of defence: a broken screen shows a way out instead of a blank window.
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null; copied: boolean }> {
  state = { error: null as Error | null, copied: false };

  static getDerivedStateFromError(error: Error) {
    return { error, copied: false };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI crashed", error, info.componentStack);
  }

  render() {
    const { error, copied } = this.state;
    if (!error) return this.props.children;
    const details = `${error.name}: ${error.message}\n${error.stack ?? ""}`;
    const copy = () => void navigator.clipboard?.writeText(details).then(() => this.setState({ copied: true }));
    return (
      <div className="grid h-full place-items-center bg-bg p-6">
        <section role="alert" aria-label="Something went wrong"
          className="flex max-w-md flex-col gap-3 rounded-xl border border-accent/40 bg-surface p-5">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-lg bg-surface-2 text-accent">
              <Bug aria-hidden="true" className="size-5" />
            </span>
            <h1 className="font-display text-base font-semibold">Something went wrong</h1>
          </div>
          <p className="text-[13px] text-muted">
            This screen hit an error it couldn't recover from. Your keyboard isn't affected. Reloading usually fixes it.
          </p>
          <p className="max-h-24 overflow-auto break-words rounded-md bg-surface-2 px-2.5 py-1.5 font-mono text-[11px] text-muted">
            {error.message}
          </p>
          <div className="flex gap-2">
            <button type="button" className={`${BUTTON} border-accent bg-accent font-medium text-on-accent hover:bg-accent`}
              onClick={() => location.reload()}>
              <RotateCw aria-hidden="true" className="size-3.5" />Reload
            </button>
            <button type="button" className={BUTTON} onClick={copy}>
              <Copy aria-hidden="true" className="size-3.5" />{copied ? "Copied" : "Copy details"}
            </button>
          </div>
        </section>
      </div>
    );
  }
}
