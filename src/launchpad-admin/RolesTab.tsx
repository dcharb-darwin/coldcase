/**
 * Roles tab — lists all roles in the current tenant+app, grouped by
 * system/custom, with edit/clone/delete actions.
 */
import { useEffect, useState } from "react";
import { adminApi } from "./api";
import { usePermission } from "./hooks";
import { RoleEditor } from "./RoleEditor";
import type { ManifestResponse, Role } from "./types";

interface Props {
  manifest: ManifestResponse;
}

export function RolesTab({ manifest }: Props) {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Role | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const canManage = usePermission("roles.manage");

  const load = async () => {
    setLoading(true);
    try {
      setRoles(await adminApi.listRoles());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const systemRoles = roles.filter((r) => r.is_system);
  const customRoles = roles.filter((r) => !r.is_system);

  const handleClone = async (role: Role) => {
    const name = window.prompt(`Clone "${role.name}" as:`, `${role.name}_copy`);
    if (!name) return;
    try {
      await adminApi.cloneRole(role.id, { new_name: name });
      load();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const handleDelete = async (role: Role) => {
    if (!window.confirm(`Delete "${role.name}"? This cannot be undone.`)) return;
    try {
      await adminApi.deleteRole(role.id);
      load();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Roles</h2>
        {canManage && (
          <button onClick={() => setShowCreate(true)} style={primaryBtn}>
            + New custom role
          </button>
        )}
      </div>

      {loading ? (
        <p>Loading…</p>
      ) : (
        <>
          <Section title="System roles (shipped with the app)">
            {systemRoles.map((r) => (
              <RoleRow
                key={r.id}
                role={r}
                canManage={canManage}
                onEdit={() => setEditing(r)}
                onClone={() => handleClone(r)}
                onDelete={() => handleDelete(r)}
              />
            ))}
          </Section>

          <Section title={`Custom roles (${customRoles.length})`}>
            {customRoles.length === 0 ? (
              <p style={{ color: "#888", fontSize: "0.875rem" }}>
                No custom roles yet. Clone a system role or create one from scratch.
              </p>
            ) : (
              customRoles.map((r) => (
                <RoleRow
                  key={r.id}
                  role={r}
                  canManage={canManage}
                  onEdit={() => setEditing(r)}
                  onClone={() => handleClone(r)}
                  onDelete={() => handleDelete(r)}
                />
              ))
            )}
          </Section>
        </>
      )}

      {showCreate && (
        <RoleEditor
          manifest={manifest}
          role={null}
          onClose={() => setShowCreate(false)}
          onSaved={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
      {editing && (
        <RoleEditor
          manifest={manifest}
          role={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: "0.8125rem", textTransform: "uppercase", opacity: 0.6, marginBottom: 8 }}>{title}</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>{children}</div>
    </div>
  );
}

function RoleRow({
  role, canManage, onEdit, onClone, onDelete,
}: {
  role: Role;
  canManage: boolean;
  onEdit: () => void;
  onClone: () => void;
  onDelete: () => void;
}) {
  const locked = role.is_system && !role.is_system_editable;
  return (
    <div style={row}>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600 }}>
          {role.name}
          {locked && <span style={lockedBadge}>🔒 locked</span>}
        </div>
        <div style={{ fontSize: "0.8125rem", color: "#666" }}>{role.description}</div>
        <div style={{ fontSize: "0.75rem", color: "#888", marginTop: 4 }}>
          {role.permissions.length} permission(s): {role.permissions.slice(0, 4).join(", ")}
          {role.permissions.length > 4 && "…"}
        </div>
      </div>
      {canManage && (
        <div style={{ display: "flex", gap: 6 }}>
          <button onClick={onEdit} style={ghostBtn}>
            {locked ? "View" : "Edit"}
          </button>
          <button onClick={onClone} style={ghostBtn}>Clone</button>
          {!role.is_system && (
            <button onClick={onDelete} style={dangerBtn}>Delete</button>
          )}
        </div>
      )}
    </div>
  );
}

const row: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 12,
  padding: 12, border: "1px solid #e5e7eb", borderRadius: 8, background: "#fff",
};
const lockedBadge: React.CSSProperties = { marginLeft: 8, fontSize: "0.6875rem", color: "#92400e" };
const primaryBtn: React.CSSProperties = { padding: "8px 14px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: "0.8125rem" };
const ghostBtn: React.CSSProperties = { padding: "6px 10px", background: "transparent", border: "1px solid #ddd", borderRadius: 6, cursor: "pointer", fontSize: "0.75rem" };
const dangerBtn: React.CSSProperties = { padding: "6px 10px", background: "transparent", color: "#dc2626", border: "1px solid #fecaca", borderRadius: 6, cursor: "pointer", fontSize: "0.75rem" };
