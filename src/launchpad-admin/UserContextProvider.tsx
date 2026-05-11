/**
 * UserContextProvider — fetches /admin/me once on mount and puts it in React
 * context. `<Can>` and `usePermission()` read from here.
 *
 * Usage:
 *   <UserContextProvider>
 *     <App />
 *   </UserContextProvider>
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { adminApi } from "./api";
import type { MeResponse } from "./types";

interface Ctx {
  me: MeResponse | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const UserContext = createContext<Ctx>({
  me: null,
  loading: true,
  error: null,
  refresh: async () => {},
});

export function UserContextProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      setMe(await adminApi.me());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
      setMe(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <UserContext.Provider value={{ me, loading, error, refresh: load }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUserContext(): Ctx {
  return useContext(UserContext);
}
