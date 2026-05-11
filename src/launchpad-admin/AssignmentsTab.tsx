/**
 * Assignments tab — lists every (user, role, scope) grant in the tenant+app.
 *
 * Assignment creation supports multi-scope-type apps: admins pick a scope TYPE
 * first ("Library" or "Individual SOP") then the scope VALUE. Leaving scope
 * blank creates a tenant-wide assignment.
 */
import { useEffect, useState } from "react";
import { adminApi } from "./api";
import { usePermission } from "./hooks";
import { useUserContext } from "./UserContextProvider";
import { impersonation } from "./impersonation";
import type { ManifestResponse, Role, RoleAssignment } from "./types";

interface Props {
  manifest: ManifestResponse;
  /** Optional — map user_id → display string. Falls back to the raw id. */
  resolveUser?: (user_id: string) => string;
}

export function AssignmentsTab({ manifest, resolveUser }: Props) {
  const [rows, setRows] = useState<RoleAssignment[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const canManage = usePermission("roles.manage");
  const { me } = useUserContext();
  const canImpersonate = !!me?.is_super_admin;

  const load = async () => {
    setLoading(true);
    try {
      const [a, r] = await Promise.all([adminApi.listAssignments(), adminApi.listRoles()]);
      setRows(a);
      setRoles(r);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const revoke = async (id: string) => {
    if (!window.confirm("Revoke this assignment?")) return;
    await adminApi.deleteAssignment(id);
    load();
  };

  const startImpersonate = async (userId: string) => {
    if (!window.confirm(
      `Impersonate user ${userId}?\n\n` +
      "The UI will render as this user until you click Exit in the banner at the top. " +
      "Actions you take during impersonation run as them and are audited."
    )) return;
    try {
      await adminApi.impersonateStart(userId);
    } catch (e) {
      alert("Impersonate failed: " + (e as Error).message);
      return;
    }
    impersonation.set(userId);
    window.location.reload();
  };

  const hasScopes = manifest.scope_types && manifest.scope_types.length > 0;
  const scopeLabel = (type: string | null) =>
    manifest.scope_types.find((s) => s.id === type)?.label ?? type ?? "—";

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Role assignments</h2>
        <div style={{ display: "flex", gap: 8 }}>
          {canImpersonate && <ImpersonateArbitraryUser onStart={startImpersonate} />}
          {canManage && (
            <button onClick={() => setShowCreate(true)} style={primaryBtn}>+ Assign role</button>
          )}
        </div>
      </div>

      {loading ? (
        <p>Loading…</p>
      ) : rows.length === 0 ? (
        <p style={{ color: "#888" }}>No assignments yet.</p>
      ) : (
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>User</th>
              <th style={th}>Role</th>
              {hasScopes && <th style={th}>Scope</th>}
              <th style={th}>Granted</th>
              {(canManage || canImpersonate) && <th style={th}></th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id}>
                <td style={td}>{resolveUser ? resolveUser(a.user_id) : a.user_id}</td>
                <td style={td}>{a.role_name}</td>
                {hasScopes && (
                  <td style={td}>
                    {a.scope_id ? (
                      <span>
                        <strong>{scopeLabel(a.scope_type)}</strong>{" "}
                        <code style={{ fontSize: "0.75rem", color: "#666" }}>{a.scope_id}</code>
                      </span>
                    ) : (
                      <span style={{ color: "#888" }}>tenant-wide</span>
                    )}
                  </td>
                )}
                <td style={td}>{a.granted_at?.slice(0, 10) ?? ""}</td>
                {(canManage || canImpersonate) && (
                  <td style={td}>
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                      {canImpersonate && (
                        <button
                          onClick={() => startImpersonate(a.user_id)}
                          style={impersonateBtn}
                          title="Render the UI as this user (SA-only)"
                        >
                          🎭 Impersonate
                        </button>
                      )}
                      {canManage && (
                        <button onClick={() => revoke(a.id)} style={dangerBtn}>Revoke</button>
                      )}
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showCreate && (
        <AssignmentCreator
          roles={roles}
          manifest={manifest}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load(); }}
        />
      )}
    </div>
  );
}

function AssignmentCreator({
  roles, manifest, onClose, onCreated,
}: {
  roles: Role[];
  manifest: ManifestResponse;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [userId, setUserId] = useState("");
  const [roleId, setRoleId] = useState(roles[0]?.id ?? "");
  const [scopeType, setScopeType] = useState<string>("");   // "" = tenant-wide
  const [scopeId, setScopeId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await adminApi.createAssignment({
        user_id: userId.trim(),
        role_id: roleId,
        scope_type: scopeType || null,
        scope_id: scopeType ? scopeId.trim() || null : null,
      });
      onCreated();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const selectedScope = manifest.scope_types.find((s) => s.id === scopeType);

  return (
    <div style={overlay}>
      <div style={modal}>
        <h3 style={{ margin: "0 0 16px 0" }}>Assign role to user</h3>

        <label style={label}>User</label>
        <input
          style={input}
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="user_id (from Govern)"
        />
        <div style={hint}>
          In prod, this will be a directory search. Today, paste the Govern
          user_id (dev user: <code>dev-local-user</code>).
        </div>

        <label style={label}>Role</label>
        <select style={input} value={roleId} onChange={(e) => setRoleId(e.target.value)}>
          {roles.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}{r.description ? ` — ${r.description.slice(0, 60)}${r.description.length > 60 ? "…" : ""}` : ""}
            </option>
          ))}
        </select>

        {manifest.scope_types.length > 0 && (
          <>
            <label style={label}>Scope</label>
            <select
              style={input}
              value={scopeType}
              onChange={(e) => { setScopeType(e.target.value); setScopeId(""); }}
            >
              <option value="">Tenant-wide — applies everywhere</option>
              {manifest.scope_types.map((st) => (
                <option key={st.id} value={st.id}>
                  Scoped to a specific {st.label.toLowerCase()}
                </option>
              ))}
            </select>
            {selectedScope && (
              <>
                <div style={hint}>
                  {selectedScope.description ||
                    `Pick the ${selectedScope.label.toLowerCase()} this role applies to.`}
                  {selectedScope.list_endpoint && (
                    <>
                      {" "}See options:{" "}
                      <code style={{ fontSize: "0.7rem" }}>GET {selectedScope.list_endpoint}</code>
                    </>
                  )}
                </div>
                <input
                  style={input}
                  value={scopeId}
                  onChange={(e) => setScopeId(e.target.value)}
                  placeholder={`${selectedScope.label} id`}
                />
              </>
            )}
          </>
        )}

        {error && <div style={errorBox}>{error}</div>}

        <div style={footer}>
          <div style={{ flex: 1 }} />
          <button onClick={onClose} disabled={saving} style={ghostBtn}>Cancel</button>
          <button
            onClick={save}
            disabled={saving || !userId || !roleId || (!!scopeType && !scopeId)}
            style={primaryBtn}
          >
            {saving ? "Saving…" : "Assign"}
          </button>
        </div>
      </div>
    </div>
  );
}

const table: React.CSSProperties = { width: "100%", borderCollapse: "collapse" };
const th: React.CSSProperties = { textAlign: "left", padding: "8px 12px", borderBottom: "1px solid #e5e7eb", fontSize: "0.75rem", textTransform: "uppercase", color: "#666" };
const td: React.CSSProperties = { padding: "10px 12px", borderBottom: "1px solid #f1f5f9", fontSize: "0.875rem" };
const overlay: React.CSSProperties = { position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10000 };
const modal: React.CSSProperties = { background: "#fff", borderRadius: 12, padding: 24, width: "min(500px, 92vw)", display: "flex", flexDirection: "column", gap: 6 };
const label: React.CSSProperties = { fontWeight: 600, fontSize: "0.8125rem", marginTop: 10 };
const input: React.CSSProperties = { padding: 8, border: "1px solid #ddd", borderRadius: 6, fontSize: "0.875rem", fontFamily: "inherit" };
const hint: React.CSSProperties = { fontSize: "0.75rem", color: "#666", marginTop: 2 };
const errorBox: React.CSSProperties = { background: "#fee2e2", color: "#991b1b", padding: 8, borderRadius: 6, fontSize: "0.8125rem", marginTop: 10 };
const footer: React.CSSProperties = { display: "flex", gap: 8, paddingTop: 12, borderTop: "1px solid #eee", marginTop: 16 };
const primaryBtn: React.CSSProperties = { padding: "8px 14px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: "0.8125rem" };
const ghostBtn: React.CSSProperties = { padding: "6px 10px", background: "transparent", border: "1px solid #ddd", borderRadius: 6, cursor: "pointer", fontSize: "0.75rem" };
const dangerBtn: React.CSSProperties = { padding: "4px 10px", background: "transparent", color: "#dc2626", border: "1px solid #fecaca", borderRadius: 6, cursor: "pointer", fontSize: "0.75rem" };
const impersonateBtn: React.CSSProperties = { padding: "4px 10px", background: "transparent", color: "#b45309", border: "1px solid #fbbf24", borderRadius: 6, cursor: "pointer", fontSize: "0.75rem", fontWeight: 600 };

function ImpersonateArbitraryUser({ onStart }: { onStart: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  if (!open) {
    return (
      <button onClick={() => setOpen(true)} style={impersonateBtn}>
        🎭 Impersonate…
      </button>
    );
  }
  return (
    <div style={{ display: "flex", gap: 4 }}>
      <input
        autoFocus
        placeholder="user_id"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && value.trim()) onStart(value.trim()); }}
        style={{ padding: "4px 8px", border: "1px solid #fbbf24", borderRadius: 6, fontSize: "0.75rem" }}
      />
      <button
        onClick={() => value.trim() && onStart(value.trim())}
        disabled={!value.trim()}
        style={impersonateBtn}
      >
        Start
      </button>
      <button onClick={() => { setOpen(false); setValue(""); }} style={ghostBtn}>Cancel</button>
    </div>
  );
}
