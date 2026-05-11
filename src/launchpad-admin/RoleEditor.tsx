/**
 * RoleEditor — create or edit a role using plain English.
 *
 * Layout:
 *   Role name + description
 *   ── 📋 "People with this role can:" live-updating capability list ──
 *   Grouped capability checkboxes with human labels + descriptions
 *   ▸ Advanced — toggle to reveal the tech permission ids
 *
 * Locked system roles (e.g. `admin` with `is_system_editable=false`) render
 * read-only with a hint to clone instead.
 */
import { useEffect, useMemo, useState } from "react";
import { adminApi } from "./api";
import type { ManifestResponse, Role } from "./types";

interface Props {
  manifest: ManifestResponse;
  /** Existing role when editing; null when creating. */
  role: Role | null;
  onClose: () => void;
  onSaved: () => void;
}

export function RoleEditor({ manifest, role, onClose, onSaved }: Props) {
  const [name, setName] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [perms, setPerms] = useState<Set<string>>(new Set(role?.permissions ?? []));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const locked = !!role?.is_system && !role.is_system_editable;

  useEffect(() => {
    setName(role?.name ?? "");
    setDescription(role?.description ?? "");
    setPerms(new Set(role?.permissions ?? []));
  }, [role]);

  const grouped = useMemo(() => {
    const g: Record<string, Array<[string, { label: string; description?: string }]>> = {};
    for (const [key, meta] of Object.entries(manifest.permissions)) {
      (g[meta.group] ||= []).push([key, meta]);
    }
    return g;
  }, [manifest]);

  /** Human sentences for currently-granted capabilities, sorted. */
  const capabilitySentences = useMemo(
    () =>
      [...perms]
        .map((p) => manifest.permissions[p]?.label)
        .filter((l): l is string => !!l)
        .sort(),
    [perms, manifest]
  );

  const toggle = (perm: string) => {
    if (locked) return;
    const next = new Set(perms);
    next.has(perm) ? next.delete(perm) : next.add(perm);
    setPerms(next);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      if (role) {
        await adminApi.updateRole(role.id, {
          name,
          description,
          permissions: [...perms],
        });
      } else {
        await adminApi.createRole({ name, description, permissions: [...perms] });
      }
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!role || !role.is_system) return;
    if (!window.confirm(`Reset "${role.name}" to manifest defaults?`)) return;
    setSaving(true);
    try {
      const updated = await adminApi.resetRole(role.id);
      setPerms(new Set(updated.permissions));
      setName(updated.name);
      setDescription(updated.description);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={overlay}>
      <div style={modal}>
        <div style={header}>
          <h3 style={{ margin: 0 }}>
            {role ? `Edit role: ${role.name}` : "New custom role"}
            {role?.is_system && <span style={badge}>system</span>}
            {locked && <span style={{ ...badge, background: "#fef3c7" }}>🔒 locked — clone to customize</span>}
          </h3>
          <button onClick={onClose} style={closeBtn}>×</button>
        </div>

        <label style={label}>Role name</label>
        <input
          style={input}
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={locked || role?.is_system}
          placeholder="e.g. HR Department Editor"
        />

        <label style={label}>Description (what this role is for)</label>
        <textarea
          style={{ ...input, minHeight: 50 }}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={locked}
          placeholder="e.g. For HR staff who need to edit SOPs only within the HR library."
        />

        {/* ── Live natural-language summary ─────────────────────────────── */}
        <div style={summary}>
          <div style={{ fontWeight: 700, fontSize: "0.8125rem", marginBottom: 6 }}>
            📋 People with this role can:
          </div>
          {capabilitySentences.length === 0 ? (
            <div style={{ fontSize: "0.8125rem", color: "#888", fontStyle: "italic" }}>
              Nothing yet — check capabilities below.
            </div>
          ) : (
            <ul style={summaryList}>
              {capabilitySentences.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          )}
        </div>

        <label style={label}>Capabilities</label>
        <div style={{ overflowY: "auto", flex: 1, padding: "4px 0" }}>
          {Object.entries(grouped).map(([group, items]) => (
            <div key={group} style={{ marginBottom: 16 }}>
              <div style={groupHeader}>{group}</div>
              {items.map(([perm, meta]) => (
                <label key={perm} style={permRow}>
                  <input
                    type="checkbox"
                    checked={perms.has(perm)}
                    onChange={() => toggle(perm)}
                    disabled={locked}
                    style={{ marginTop: 3 }}
                  />
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <span style={{ fontSize: "0.875rem" }}>{meta.label}</span>
                    {meta.description && (
                      <span style={{ fontSize: "0.75rem", color: "#666" }}>
                        {meta.description}
                      </span>
                    )}
                    {showAdvanced && (
                      <code style={{ fontSize: "0.6875rem", color: "#94a3b8", fontFamily: "ui-monospace, monospace" }}>
                        {perm}
                      </code>
                    )}
                  </div>
                </label>
              ))}
            </div>
          ))}
        </div>

        <label style={advancedToggle}>
          <input
            type="checkbox"
            checked={showAdvanced}
            onChange={() => setShowAdvanced(!showAdvanced)}
          />
          Show permission ids (advanced)
        </label>

        {error && <div style={errorBox}>{error}</div>}

        <div style={footer}>
          {role?.is_system && !locked && (
            <button onClick={handleReset} disabled={saving} style={ghostBtn}>
              Reset to defaults
            </button>
          )}
          <div style={{ flex: 1 }} />
          <button onClick={onClose} disabled={saving} style={ghostBtn}>Cancel</button>
          {!locked && (
            <button onClick={handleSave} disabled={saving || !name.trim()} style={primaryBtn}>
              {saving ? "Saving…" : "Save"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Inline styles ──
const overlay: React.CSSProperties = {
  position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
  display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10000,
};
const modal: React.CSSProperties = {
  background: "#fff", borderRadius: 12, padding: 24,
  width: "min(640px, 92vw)", maxHeight: "92vh",
  display: "flex", flexDirection: "column", gap: 6,
};
const header: React.CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 };
const closeBtn: React.CSSProperties = { background: "none", border: "none", fontSize: 24, cursor: "pointer" };
const label: React.CSSProperties = { fontWeight: 600, fontSize: "0.8125rem", marginTop: 10 };
const input: React.CSSProperties = { padding: 8, border: "1px solid #ddd", borderRadius: 6, fontSize: "0.875rem", fontFamily: "inherit" };
const badge: React.CSSProperties = { marginLeft: 8, background: "#e5e7eb", padding: "2px 8px", borderRadius: 10, fontSize: "0.6875rem", fontWeight: 600 };
const summary: React.CSSProperties = {
  marginTop: 12, padding: "12px 14px",
  background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 8,
};
const summaryList: React.CSSProperties = { margin: 0, paddingLeft: 20, fontSize: "0.8125rem", lineHeight: 1.5 };
const groupHeader: React.CSSProperties = { fontWeight: 700, fontSize: "0.75rem", textTransform: "uppercase", opacity: 0.6, marginBottom: 6, letterSpacing: "0.02em" };
const permRow: React.CSSProperties = { display: "flex", alignItems: "flex-start", gap: 10, padding: "6px 0", cursor: "pointer" };
const advancedToggle: React.CSSProperties = { display: "flex", alignItems: "center", gap: 6, fontSize: "0.75rem", color: "#666", padding: "4px 0" };
const errorBox: React.CSSProperties = { background: "#fee2e2", color: "#991b1b", padding: 8, borderRadius: 6, fontSize: "0.8125rem" };
const footer: React.CSSProperties = { display: "flex", gap: 8, paddingTop: 12, borderTop: "1px solid #eee", marginTop: 4 };
const primaryBtn: React.CSSProperties = { padding: "8px 16px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 600 };
const ghostBtn: React.CSSProperties = { padding: "8px 16px", background: "transparent", border: "1px solid #ddd", borderRadius: 6, cursor: "pointer" };
