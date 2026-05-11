/**
 * SSR / Safari-private-mode safe localStorage helpers.
 *
 * localStorage can throw in Safari private mode (quota/security) and is
 * absent under SSR. Writes are best-effort; reads fall back to the
 * provided default.
 *
 * Used by every persisted-state surface (nav-collapse, viewMode toggles,
 * dock positions) so the guard pattern isn't reinvented per site.
 *
 * Paired with `useViewMode` (src/lib/useViewMode.ts) for typed
 * string-union presentation toggles.
 */

export function readLocalStorage(key: string, fallback: string | null = null): string | null {
  if (typeof localStorage === "undefined") return fallback;
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : v;
  } catch {
    return fallback;
  }
}

export function writeLocalStorage(key: string, value: string): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(key, value);
  } catch {
    /* best-effort — private mode throws */
  }
}
