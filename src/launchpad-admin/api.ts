/**
 * Admin API client. Thin wrapper around fetch so the pattern doesn't pin apps
 * to a particular HTTP library. Each app can adapt to its own axios/tanstack
 * setup — only `apiBase` needs pointing.
 */
import type {
  AssistResponse,
  ManifestResponse,
  MeResponse,
  Role,
  RoleAssignment,
  RoleMapping,
} from "./types";

let apiBase = "/admin";

/** Host apps can inject extra headers on every admin request (e.g. the SOP
 * Builder's SA impersonation header). Keeps this package app-agnostic. */
let extraHeaders: () => Record<string, string> = () => ({});

export function configureAdminApi(base: string) {
  apiBase = base.replace(/\/+$/, "");
}

export function configureAdminHeaders(provider: () => Record<string, string>) {
  extraHeaders = provider;
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { ...extraHeaders() };
  if (body) headers["Content-Type"] = "application/json";
  const res = await fetch(`${apiBase}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    credentials: "include",
  });
  if (!res.ok) {
    let detail: string = res.statusText;
    try {
      const body = await res.json();
      // FastAPI's `detail` is usually a string, but for 422 validation errors
      // it's an array of {loc, msg, type} objects. Render both cleanly so
      // callers never see "[object Object]".
      const raw = body?.detail;
      if (typeof raw === "string") detail = raw;
      else if (raw) detail = JSON.stringify(raw);
    } catch {}
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json();
}

export const adminApi = {
  manifest: () => req<ManifestResponse>("GET", "/manifest"),
  me: () => req<MeResponse>("GET", "/me"),

  listRoles: () => req<Role[]>("GET", "/roles"),
  getRole: (id: string) => req<Role>("GET", `/roles/${id}`),
  createRole: (body: { name: string; description?: string; permissions: string[] }) =>
    req<Role>("POST", "/roles", body),
  updateRole: (id: string, body: { name?: string; description?: string; permissions?: string[] }) =>
    req<Role>("PUT", `/roles/${id}`, body),
  deleteRole: (id: string) => req<{ deleted: string }>("DELETE", `/roles/${id}`),
  resetRole: (id: string) => req<Role>("POST", `/roles/${id}/reset`),
  cloneRole: (id: string, body: { new_name: string; description?: string }) =>
    req<Role>("POST", `/roles/${id}/clone`, body),

  listAssignments: () => req<RoleAssignment[]>("GET", "/assignments"),
  createAssignment: (body: {
    user_id: string;
    role_id: string;
    scope_type?: string | null;
    scope_id?: string | null;
  }) => req<RoleAssignment>("POST", "/assignments", body),
  deleteAssignment: (id: string) => req<{ deleted: string }>("DELETE", `/assignments/${id}`),

  listMappings: () => req<RoleMapping[]>("GET", "/mappings"),
  createMapping: (body: {
    match_type: "ad_group" | "department";
    match_value: string;
    role_id: string;
    scope_type?: string | null;
    scope_id?: string | null;
    notes?: string;
  }) => req<RoleMapping>("POST", "/mappings", body),
  deleteMapping: (id: string) => req<{ deleted: string }>("DELETE", `/mappings/${id}`),

  /** AI assistant — plain-English prompt → proposed actions. */
  assist: (prompt: string) => req<AssistResponse>("POST", "/assist", { prompt }),

  /** SA-only — audit the start of an impersonation session. The actual
   * header swap is done by the host app's API client. */
  impersonateStart: (targetUserId: string) =>
    req<{ impersonating: string; sa_user_id: string }>(
      "POST", "/impersonate/start", { target_user_id: targetUserId }
    ),
  impersonateStop: () =>
    req<{ was_impersonating: boolean }>("POST", "/impersonate/stop"),
};
