/** Hash-based route paths (no `#` prefix). Centralized so components don't string-concat. */

export const ROUTES = {
  dashboard: "/",
  cases: "/cases",
  casePrefix: "/cases/",
  audit: "/audit",
  admin: "/admin",
} as const;

export function isCaseListRoute(path: string): boolean {
  return stripHashQuery(path) === ROUTES.cases;
}

export function isCaseDetailRoute(path: string): boolean {
  return stripHashQuery(path).startsWith(ROUTES.casePrefix);
}

export function caseIdFromRoute(path: string): string | null {
  if (!isCaseDetailRoute(path)) return null;
  return stripHashQuery(path).slice(ROUTES.casePrefix.length).split("/")[0] || null;
}

/** `/cases/:caseId/reports/:reportId` — Phase A · PR 3 report workspace. */
export function isReportDetailRoute(path: string): boolean {
  return /^\/cases\/[^/?]+\/reports\/[^/?]+/.test(stripHashQuery(path));
}

export function reportRouteIds(path: string): { caseId: string; reportId: string } | null {
  const m = stripHashQuery(path).match(/^\/cases\/([^/]+)\/reports\/([^/]+)/);
  if (!m) return null;
  return { caseId: m[1]!, reportId: m[2]! };
}

export function reportRoute(caseId: string, reportId: string): string {
  return `${ROUTES.casePrefix}${caseId}/reports/${reportId}`;
}

/** Parse `?k=v&k2=v2` from the end of a hash path. URLSearchParams ignores
 *  the leading "?", and decodes percent-encoded values. Safe on paths
 *  without a query string (returns an empty object). */
export function parseHashQuery(path: string): Record<string, string> {
  const qIdx = path.indexOf("?");
  if (qIdx < 0) return {};
  const params = new URLSearchParams(path.slice(qIdx + 1));
  const out: Record<string, string> = {};
  params.forEach((v, k) => { out[k] = v; });
  return out;
}

/** Path without the query suffix — for the case-id parser etc. */
export function stripHashQuery(path: string): string {
  const qIdx = path.indexOf("?");
  return qIdx < 0 ? path : path.slice(0, qIdx);
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
