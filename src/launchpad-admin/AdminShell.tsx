/**
 * AdminShell — the top-level admin page for a Launchpad app.
 *
 * Tabs:
 *   - My Access       (always visible)
 *   - Roles           (requires admin.view)
 *   - Assignments     (requires admin.view)
 *
 * The "admin.view" gate hides the last two tabs from ordinary users. Inside
 * each tab, further "roles.manage" checks hide management controls — so an
 * admin.view-only user (e.g. an auditor) can browse without editing.
 */
import { useEffect, useState } from "react";
import { adminApi, configureAdminApi } from "./api";
import { usePermission } from "./hooks";
import { useUserContext } from "./UserContextProvider";
import { AssignmentsTab } from "./AssignmentsTab";
import { AssistantTab } from "./AssistantTab";
import { MappingsTab } from "./MappingsTab";
import { MyAccessTab } from "./MyAccessTab";
import { RolesTab } from "./RolesTab";
import type { ManifestResponse } from "./types";

interface Props {
  /** Optional — override the default /admin API base. */
  apiBase?: string;
  /** Optional — resolve user_ids to display strings in the Assignments tab. */
  resolveUser?: (user_id: string) => string;
}

type TabId = "access" | "assistant" | "roles" | "assignments" | "mappings";

export function AdminShell({ apiBase, resolveUser }: Props) {
  useEffect(() => {
    if (apiBase) configureAdminApi(apiBase);
  }, [apiBase]);

  const [manifest, setManifest] = useState<ManifestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("access");
  const { me, loading: meLoading } = useUserContext();

  const canViewAdmin = usePermission("admin.view");

  useEffect(() => {
    adminApi
      .manifest()
      .then(setManifest)
      .catch((e) => setError((e as Error).message));
  }, []);

  if (meLoading || !manifest) return <div style={{ padding: 24 }}>Loading admin…</div>;
  if (error) return <div style={{ padding: 24, color: "#dc2626" }}>Error: {error}</div>;
  if (!me) return <div style={{ padding: 24 }}>Not authenticated.</div>;

  const canManageRoles = usePermission("roles.manage");

  const tabs: Array<{ id: TabId; label: string; visible: boolean }> = [
    { id: "access", label: "My Access", visible: true },
    { id: "assistant", label: "✨ Assistant", visible: canManageRoles },
    { id: "roles", label: "Roles", visible: canViewAdmin },
    { id: "assignments", label: "Assignments", visible: canViewAdmin },
    { id: "mappings", label: "AD Mappings", visible: canViewAdmin },
  ];
  const visibleTabs = tabs.filter((t) => t.visible);

  return (
    <div style={shell}>
      <div style={header}>
        <h1 style={{ margin: 0, fontSize: "1.25rem" }}>
          {manifest.display_name} — Admin
        </h1>
        <span style={{ fontSize: "0.8125rem", color: "#666" }}>
          Tenant: {me.tenant_name || me.tenant_id}
          {me.is_super_admin && <span style={saBadge}>SA</span>}
        </span>
      </div>

      <nav style={tabBar}>
        {visibleTabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{ ...tabBtn, ...(tab === t.id ? tabActive : {}) }}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div style={{ flex: 1, overflow: "auto" }}>
        {tab === "access" && <MyAccessTab manifest={manifest} />}
        {tab === "roles" && canViewAdmin && <RolesTab manifest={manifest} />}
        {tab === "assignments" && canViewAdmin && (
          <AssignmentsTab manifest={manifest} resolveUser={resolveUser} />
        )}
        {tab === "mappings" && canViewAdmin && (
          <MappingsTab manifest={manifest} />
        )}
        {tab === "assistant" && canManageRoles && <AssistantTab />}
      </div>
    </div>
  );
}

const shell: React.CSSProperties = {
  display: "flex", flexDirection: "column", height: "100%", minHeight: 500,
  background: "#f8fafc",
};
const header: React.CSSProperties = {
  display: "flex", alignItems: "center", justifyContent: "space-between",
  padding: "16px 24px", borderBottom: "1px solid #e5e7eb", background: "#fff",
};
const saBadge: React.CSSProperties = {
  marginLeft: 8, background: "#2563eb", color: "#fff",
  padding: "2px 8px", borderRadius: 10, fontSize: "0.6875rem", fontWeight: 700,
};
const tabBar: React.CSSProperties = {
  display: "flex", gap: 4, padding: "0 16px", borderBottom: "1px solid #e5e7eb", background: "#fff",
};
const tabBtn: React.CSSProperties = {
  padding: "10px 16px", background: "transparent", border: "none",
  borderBottom: "2px solid transparent", cursor: "pointer",
  fontSize: "0.875rem", fontWeight: 500, color: "#666",
};
const tabActive: React.CSSProperties = {
  color: "#2563eb", borderBottomColor: "#2563eb", fontWeight: 600,
};
