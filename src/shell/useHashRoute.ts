import { useEffect, useState } from "react";
import { normalizeHashPath } from "./routes";

/** Current hash route path, synced on `hashchange`. */
export function useHashRoute(): string {
  const [path, setPath] = useState(() => normalizeHashPath(window.location.hash));

  useEffect(() => {
    const onHashChange = () => setPath(normalizeHashPath(window.location.hash));
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  return path;
}
