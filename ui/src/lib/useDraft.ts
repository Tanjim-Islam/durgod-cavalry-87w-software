import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import type { RGB } from "@/bridge/types";

export const STALE_MSG = "Colors changed on the keyboard, unsaved edits were discarded";

// Local unsaved edits over a saved color list. Drops itself if the saved base changes by value.
export function useDraft(base: RGB[] | null | undefined, onChange?: (d: RGB[] | null) => void) {
  const [draft, setDraft] = useState<RGB[] | null>(null);
  const [saving, setSaving] = useState(false);
  const cur = useRef<RGB[] | null>(null);   // latest draft, updated synchronously for fast drags
  const snap = useRef<string | null>(null); // base at the moment the draft started
  const busy = useRef(false);
  const notify = useRef(onChange); notify.current = onChange;
  const baseKey = JSON.stringify(base ?? null);

  const set = (next: RGB[] | null) => { cur.current = next; if (!next) snap.current = null; setDraft(next); notify.current?.(next); };
  const edit = (fn: (c: RGB[]) => RGB[]) => {
    if (!base || busy.current) return;
    if (!cur.current) snap.current = baseKey;
    set(fn(cur.current ?? base));
  };
  const discard = () => { if (cur.current && !busy.current) set(null); };
  const save = async (fn: (d: RGB[]) => unknown) => {
    if (!cur.current || busy.current) return;
    busy.current = true; setSaving(true);
    try { if ((await fn(cur.current)) !== false) set(null); }
    finally { busy.current = false; setSaving(false); }
  };

  useEffect(() => {
    // A save changes the base itself, so only outside changes count.
    if (cur.current && !busy.current && snap.current !== baseKey) { set(null); toast.info(STALE_MSG); }
  }, [baseKey]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => notify.current?.(null), []);

  return { draft, shown: draft ?? base ?? null, saving, edit, discard, save };
}
