import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

type ShellChromeValue = {
  /** Optional label for the current detail page (e.g. employee name once loaded). */
  detailLabel: string | null;
  setDetailLabel: (value: string | null) => void;
};

const ShellChromeContext = createContext<ShellChromeValue | null>(null);

const NAV_COLLAPSED_KEY = "coldcase-shell-nav-collapsed";

export function readNavCollapsedFromStorage(): boolean {
  try {
    return typeof localStorage !== "undefined" && localStorage.getItem(NAV_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

export function writeNavCollapsedToStorage(collapsed: boolean): void {
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(NAV_COLLAPSED_KEY, collapsed ? "1" : "0");
    }
  } catch {
    /* ignore */
  }
}

export function ShellChromeProvider({ children }: { children: ReactNode }) {
  const [detailLabel, setDetailLabelState] = useState<string | null>(null);
  const setDetailLabel = useCallback((value: string | null) => setDetailLabelState(value), []);
  const value = useMemo<ShellChromeValue>(() => ({ detailLabel, setDetailLabel }), [detailLabel, setDetailLabel]);
  return <ShellChromeContext.Provider value={value}>{children}</ShellChromeContext.Provider>;
}

export function useShellChrome(): ShellChromeValue {
  const ctx = useContext(ShellChromeContext);
  if (!ctx) throw new Error("useShellChrome must be used within ShellChromeProvider");
  return ctx;
}
