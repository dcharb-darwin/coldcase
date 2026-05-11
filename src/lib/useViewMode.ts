/**
 * useViewMode — localStorage-persisted toggle between two presentations
 * of the same collection (typically "cards" vs "list"). Implements
 * Launchpad design principle P2: "Cards + list toggle" with a toggle
 * that persists across sessions.
 *
 * Usage:
 *   const [mode, setMode] = useViewMode("app.page.viewMode", "cards");
 *
 * The key should be app-scoped (e.g. "sop-builder.library.viewMode") so
 * concurrent Launchpad apps on the same origin don't collide.
 *
 * `allowed` is a runtime safety filter — if localStorage holds a stale
 * value from a prior app version (or another app on the same origin),
 * fall back to the default instead of typing into an invalid state.
 */

import { useCallback, useState } from "react";
import { readLocalStorage, writeLocalStorage } from "./storage";

export function useViewMode<M extends string>(
  storageKey: string,
  defaultMode: M,
  allowed?: readonly M[],
): [M, (next: M) => void] {
  const [mode, _setMode] = useState<M>(() => {
    const raw = readLocalStorage(storageKey);
    if (raw == null) return defaultMode;
    if (allowed && !allowed.includes(raw as M)) return defaultMode;
    return raw as M;
  });

  const setMode = useCallback(
    (next: M) => {
      _setMode((prev) => {
        if (prev === next) return prev;
        writeLocalStorage(storageKey, next);
        return next;
      });
    },
    [storageKey],
  );

  return [mode, setMode];
}
