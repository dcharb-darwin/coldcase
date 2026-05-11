/**
 * My Access — read-only view of the current user's roles and effective
 * permissions. Shown to every authenticated user, demystifies "why can't I
 * do X?" without needing to email IT.
 */
import { useUserContext } from "./UserContextProvider";
import type { ManifestResponse } from "./types";

interface Props {
  manifest: ManifestResponse;
}

export function MyAccessTab({ manifest }: Props) {
  const { me } = useUserContext();
  if (!me) return null;

  const groupedPerms: Record<string, string[]> = {};
  for (const perm of me.permissions) {
    const group = manifest.permissions[perm]?.group ?? "Other";
    (groupedPerms[group] ||= []).push(perm);
  }

  return (
    <div style={{ padding: 16 }}>
      <h2 style={{ marginTop: 0 }}>My Access</h2>
      <p style={{ color: "#666" }}>
        Your identity and effective permissions in <strong>{manifest.display_name}</strong> for tenant{" "}
        <strong>{me.tenant_name || me.tenant_id}</strong>.
      </p>

      <dl style={dl}>
        <dt>User</dt><dd>{me.first_name} {me.last_name} ({me.email})</dd>
        <dt>Super Admin</dt><dd>{me.is_super_admin ? "Yes (Govern-granted)" : "No"}</dd>
        <dt>Roles</dt>
        <dd>{me.roles.length ? me.roles.join(", ") : <span style={{ color: "#888" }}>none</span>}</dd>
      </dl>

      <h3 style={{ marginTop: 24 }}>Tenant-wide permissions</h3>
      {me.is_super_admin ? (
        <p style={{ color: "#2563eb" }}>SA bypass — every permission granted.</p>
      ) : me.permissions.length === 0 ? (
        <p style={{ color: "#888" }}>No tenant-wide permissions. Ask an admin to assign you a role.</p>
      ) : (
        <>
          {Object.entries(groupedPerms).map(([group, perms]) => (
            <div key={group} style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 600, fontSize: "0.75rem", textTransform: "uppercase", opacity: 0.6 }}>{group}</div>
              <ul style={{ margin: 4, paddingLeft: 20 }}>
                {perms.map((p) => (
                  <li key={p} style={{ fontSize: "0.875rem" }}>
                    {manifest.permissions[p]?.label ?? p}
                    <code style={{ fontSize: "0.6875rem", opacity: 0.4, marginLeft: 6 }}>{p}</code>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}

      {Object.keys(me.scoped_permissions).length > 0 && (
        <>
          <h3>Scoped permissions</h3>
          {Object.entries(me.scoped_permissions).map(([scopeKey, perms]) => {
            // Composite "<scope_type>:<scope_id>" — split + friendly-ify.
            const [scopeType, scopeId] = scopeKey.includes(":")
              ? [scopeKey.split(":")[0], scopeKey.slice(scopeKey.indexOf(":") + 1)]
              : ["", scopeKey];
            const typeLabel = manifest.scope_types.find((s) => s.id === scopeType)?.label ?? scopeType ?? "scope";
            const labels = perms
              .map((p) => manifest.permissions[p]?.label ?? p)
              .join(", ");
            return (
              <div key={scopeKey} style={{ marginBottom: 8 }}>
                <div style={{ fontWeight: 600 }}>
                  {typeLabel} <code style={{ fontSize: "0.75rem", color: "#666" }}>{scopeId}</code>
                </div>
                <div style={{ fontSize: "0.8125rem", color: "#666" }}>{labels}</div>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}

const dl: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "max-content 1fr", gap: "4px 16px", fontSize: "0.875rem",
};
