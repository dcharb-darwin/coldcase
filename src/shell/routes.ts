/** Hash-based route paths (no `#` prefix). Centralized so components don't string-concat. */

export const ROUTES = {
  dashboard: "/",
  cases: "/cases",
  casePrefix: "/cases/",
  audit: "/audit",
  admin: "/admin",
} as const;

export function isCaseListRoute(path: string): boolean {
  return path === ROUTES.cases;
}

export function isCaseDetailRoute(path: string): boolean {
  return path.startsWith(ROUTES.casePrefix);
}

export function caseIdFromRoute(path: string): string | null {
  if (!isCaseDetailRoute(path)) return null;
  return path.slice(ROUTES.casePrefix.length).split("/")[0] || null;
}

export function isAuditRoute(path: string): boolean {
  return path === ROUTES.audit || path.startsWith(`${ROUTES.audit}/`);
}

/** Normalize `window.location.hash` to a path starting with `/`. */
export function normalizeHashPath(hash: string): string {
  const raw = hash.startsWith("#") ? hash.slice(1) : hash;
  return raw || ROUTES.dashboard;
}

export function isAdminRoute(path: string): boolean {
  return path === ROUTES.admin || path.startsWith(`${ROUTES.admin}/`);
}

/** Set `window.location.hash` from an app path (leading `/` optional). */
export function setHashPath(path: string): void {
  const next = path.startsWith("/") ? path : `/${path}`;
  window.location.hash = next;
}
