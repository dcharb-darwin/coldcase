/**
 * Impersonation state — SA-only, sessionStorage-backed.
 *
 * When active, every API call automatically carries the
 * `X-Impersonate-User-Id` header so the backend middleware swaps in a
 * UserContext for the target. Clears when the tab closes (sessionStorage)
 * or when the user explicitly exits.
 */

const KEY = "impersonate_user_id";

export const impersonation = {
  get(): string | null {
    try {
      return sessionStorage.getItem(KEY) || null;
    } catch {
      return null;
    }
  },
  set(userId: string): void {
    sessionStorage.setItem(KEY, userId);
  },
  clear(): void {
    sessionStorage.removeItem(KEY);
  },
  active(): boolean {
    return !!this.get();
  },
};

/** Returns a header object to spread into fetch/axios configs.
 * Empty when not impersonating. */
export function impersonationHeader(): Record<string, string> {
  const id = impersonation.get();
  return id ? { "X-Impersonate-User-Id": id } : {};
}
