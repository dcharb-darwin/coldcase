/**
 * Mappings tab — auto-assign roles to anyone whose identity claims match a rule.
 *
 * Example: "Members of AD group `HR-Managers` get `library_editor` scoped to
 * the HR library". In prod, Govern provides the user's AD groups and
 * department via token claims; the middleware unions these mapping-derived
 * roles with direct RoleAssignments on every request.
 *
 * Local dev: set DEV_AD_GROUPS=HR-Managers,Leads and/or DEV_DEPARTMENT=IT in
 * the backend env to simulate claims without touching a real IdP.
 */
import { useEffect, useState } from "react";
import { adminApi } from "./api";
import { usePermission } from "./hooks";
import { useUserContext } from "./UserContextProvider";
import type { ManifestResponse, Role, RoleMapping } from "./types";

interface Props {
  manifest: ManifestResponse;
}

export function MappingsTab({ manifest }: Props) {
  const [rows, setRows] = useState<RoleMapping[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const canManage = usePermission("roles.manage");
  const { me } = useUserContext();

  const load = async () => {
    setLoading(true);
    try {
      const [m, r] = await Promise.all([adminApi.listMappings(), adminApi.listRoles()]);
      setRows(m);
      setRoles(r);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const revoke = async (id: string) => {
    if (!window.confirm("Delete this mapping? Users who matched it will lose the auto-assigned role on their next request.")) return;
    await adminApi.deleteMapping(id);
    load();
  };

  const scopeLabel = (type: string | null) =>
    manifest.scope_types.find((s) => s.id === type)?.label ?? type ?? "—";

  /** Render one mapping as a plain-English sentence. */
  const sentence = (m: RoleMapping) => {
    const who =
      m.match_type === "ad_group"
        ? <>members of AD group <strong>{m.match_value}</strong></>
        : <>users whose department is <strong>{m.match_value}</strong></>;
    const where = m.scope_id
      ? <> in {scopeLabel(m.scope_type)} <code style={{ fontSize: "0.75rem" }}>{m.scope_id}</code></>
      : <> tenant-wide</>;
    return <span>Everyone — {who} — gets role <strong>{m.role_name}</strong>{where}.</span>;
  };

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div>
          <h2 style={{ margin: 0 }}>Auto-assignments (AD groups & departments)</h2>
          <p style={{ margin: "4px 0 0 0", color: "#666", fontSize: "0.8125rem" }}>
            Rules that grant roles automatically based on identity claims from Govern.
            Evaluated every request — changes take effect immediately for matching users.
          </p>
        </div>
        {canManage && (
          <button onClick={() => setShowCreate(true)} style={primaryBtn}>+ New mapping</button>
        )}
      </div>

      {/* "Your claims" panel — diagnoses why mappings did/didn't fire */}
      {me && (
        <div style={claimsPanel}>
          <div style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", opacity: 0.6, marginBottom: 4 }}>
            Your identity claims
          </div>
          <div style={{ fontSize: "0.8125rem" }}>
            AD groups:{" "}
            {me.govern_roles && me.govern_roles.length > 0 ? (
              me.govern_roles.map((g) => <code key={g} style={claimPill}>{g}</code>)
            ) : (
              <span style={{ color: "#888" }}>none</span>
            )}
          </div>
          <div style={{ fontSize: "0.8125rem", marginTop: 2 }}>
            Department:{" "}
            {me.attributes && (me.attributes as any).department ? (
              <code style={claimPill}>{String((me.attributes as any).department)}</code>
            ) : (
              <span style={{ color: "#888" }}>none</span>
            )}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#666", marginTop: 6 }}>
            In dev, simulate via env vars before starting the backend:{" "}
            <code>DEV_AD_GROUPS=HR-Managers,Leads DEV_DEPARTMENT=IT npm run api</code>
          </div>
        </div>
      )}

      {loading ? (
        <p>Loading…</p>
      ) : rows.length === 0 ? (
        <p style={{ color: "#888", marginTop: 20 }}>
          No mappings yet. Create one to auto-assign a role to everyone in an AD group or department.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 16 }}>
          {rows.map((m) => (
            <div key={m.id} style={row}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: "0.9375rem", lineHeight: 1.5 }}>{sentence(m)}</div>
                {m.notes && (
                  <div style={{ fontSize: "0.75rem", color: "#888", marginTop: 4 }}>{m.notes}</div>
                )}
              </div>
              {canManage && (
                <button onClick={() => revoke(m.id)} style={dangerBtn}>Delete</button>
              )}
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <MappingCreator
          roles={roles}
          manifest={manifest}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load(); }}
        />
      )}
    </div>
  );
}

function MappingCreator({
  roles, manifest, onClose, onCreated,
}: {
  roles: Role[];
  manifest: ManifestResponse;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [matchType, setMatchType] = useState<"ad_group" | "department">("ad_group");
  const [matchValue, setMatchValue] = useState("");
  const [roleId, setRoleId] = useState(roles[0]?.id ?? "");
  const [scopeType, setScopeType] = useState("");
  const [scopeId, setScopeId] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await adminApi.createMapping({
        match_type: matchType,
        match_value: matchValue.trim(),
        role_id: roleId,
        scope_type: scopeType || null,
        scope_id: scopeType ? scopeId.trim() || null : null,
        notes: notes.trim(),
      });
      onCreated();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const selectedScope = manifest.scope_types.find((s) => s.id === scopeType);
  const selectedRole = roles.find((r) => r.id === roleId);

  // Live preview sentence
  const preview = (() => {
    if (!matchValue.trim() || !selectedRole) return null;
    const who =
      matchType === "ad_group"
        ? `members of AD group "${matchValue}"`
        : `users in department "${matchValue}"`;
    const where = scopeType
      ? ` in ${selectedScope?.label ?? scopeType} ${scopeId || "<id>"}`
      : " tenant-wide";
    return `Everyone — ${who} — will get role "${selectedRole.name}"${where}.`;
  })();

  return (
    <div style={overlay}>
      <div style={modal}>
        <h3 style={{ margin: "0 0 12px 0" }}>New auto-assignment rule</h3>

        <label style={label}>Match users by</label>
        <select style={input} value={matchType} onChange={(e) => setMatchType(e.target.value as "ad_group" | "department")}>
          <option value="ad_group">AD Group membership</option>
          <option value="department">Department claim</option>
        </select>

        <label style={label}>
          {matchType === "ad_group" ? "AD group name" : "Department name"}
        </label>
        <input
          style={input}
          value={matchValue}
          onChange={(e) => setMatchValue(e.target.value)}
          placeholder={matchType === "ad_group" ? "e.g. HR-Managers" : "e.g. HR"}
        />
        <div style={hint}>Exact match, case-sensitive.</div>

        <label style={label}>Grant role</label>
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
              <option value="">Tenant-wide</option>
              {manifest.scope_types.map((st) => (
                <option key={st.id} value={st.id}>Scoped to a specific {st.label.toLowerCase()}</option>
              ))}
            </select>
            {selectedScope && (
              <>
                <div style={hint}>
                  {selectedScope.list_endpoint && (
                    <>See ids: <code style={{ fontSize: "0.7rem" }}>GET {selectedScope.list_endpoint}</code></>
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

        <label style={label}>Notes (optional)</label>
        <input style={input} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Why this mapping exists" />

        {preview && (
          <div style={previewBox}>
            <div style={{ fontWeight: 700, fontSize: "0.75rem", marginBottom: 4 }}>📋 This rule will:</div>
            <div style={{ fontSize: "0.8125rem" }}>{preview}</div>
          </div>
        )}

        {error && <div style={errorBox}>{error}</div>}

        <div style={footer}>
          <div style={{ flex: 1 }} />
          <button onClick={onClose} disabled={saving} style={ghostBtn}>Cancel</button>
          <button
            onClick={save}
            disabled={saving || !matchValue.trim() || !roleId || (!!scopeType && !scopeId)}
            style={primaryBtn}
          >
            {saving ? "Saving…" : "Create mapping"}
          </button>
        </div>
      </div>
    </div>
  );
}

const row: React.CSSProperties = { display: "flex", alignItems: "center", gap: 12, padding: 14, border: "1px solid #e5e7eb", borderRadius: 8, background: "#fff" };
const claimsPanel: React.CSSProperties = { padding: 12, background: "#f1f5f9", border: "1px solid #e2e8f0", borderRadius: 8, marginBottom: 8 };
const claimPill: React.CSSProperties = { background: "#e0e7ff", padding: "2px 8px", borderRadius: 10, fontSize: "0.75rem", marginRight: 4 };
const overlay: React.CSSProperties = { position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10000 };
const modal: React.CSSProperties = { background: "#fff", borderRadius: 12, padding: 24, width: "min(520px, 92vw)", display: "flex", flexDirection: "column", gap: 6, maxHeight: "92vh", overflow: "auto" };
const label: React.CSSProperties = { fontWeight: 600, fontSize: "0.8125rem", marginTop: 10 };
const input: React.CSSProperties = { padding: 8, border: "1px solid #ddd", borderRadius: 6, fontSize: "0.875rem", fontFamily: "inherit" };
const hint: React.CSSProperties = { fontSize: "0.75rem", color: "#666", marginTop: 2 };
const errorBox: React.CSSProperties = { background: "#fee2e2", color: "#991b1b", padding: 8, borderRadius: 6, fontSize: "0.8125rem", marginTop: 10 };
const previewBox: React.CSSProperties = { marginTop: 12, padding: 10, background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 8 };
const footer: React.CSSProperties = { display: "flex", gap: 8, paddingTop: 12, borderTop: "1px solid #eee", marginTop: 16 };
const primaryBtn: React.CSSProperties = { padding: "8px 14px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: "0.8125rem" };
const ghostBtn: React.CSSProperties = { padding: "6px 10px", background: "transparent", border: "1px solid #ddd", borderRadius: 6, cursor: "pointer", fontSize: "0.75rem" };
const dangerBtn: React.CSSProperties = { padding: "6px 10px", background: "transparent", color: "#dc2626", border: "1px solid #fecaca", borderRadius: 6, cursor: "pointer", fontSize: "0.75rem" };
