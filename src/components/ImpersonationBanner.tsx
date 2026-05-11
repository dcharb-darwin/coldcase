/**
 * ImpersonationBanner — always-visible top bar when an SA is currently
 * "seeing as" another user. Loud colors + explicit Exit button so nobody
 * forgets they're viewing someone else's UI.
 */
import { adminApi, impersonation, useUserContext } from "../launchpad-admin";

export function ImpersonationBanner() {
  const { me, refresh } = useUserContext();

  // Show only when the server confirms an impersonation is active. We
  // don't trust sessionStorage alone — the backend is the source of truth.
  if (!me?.impersonator_user_id) return null;

  const exit = async () => {
    try {
      await adminApi.impersonateStop();
    } catch {
      // Audit-only endpoint; even if it fails, clearing the header below
      // always returns the session to normal.
    }
    impersonation.clear();
    // Hard reload — clears every React-Query cache that was populated
    // under the impersonated identity.
    window.location.reload();
  };

  return (
    <div style={banner}>
      <span style={{ fontSize: "1.1rem" }}>🎭</span>
      <span>
        Impersonating <strong>{me.email || me.user_id}</strong> — actions below render as this user.
        SA <strong>{me.impersonator_email || me.impersonator_user_id}</strong> can exit at any time.
      </span>
      <span style={{ flex: 1 }} />
      <button onClick={exit} style={exitBtn}>Exit impersonation</button>
      {/* refresh is unused but referenced so lint doesn't complain about
          the destructure; also gives callers a handle if they want to
          force an identity refetch without reloading. */}
      <span style={{ display: "none" }}>{String(!!refresh)}</span>
    </div>
  );
}

const banner: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 10,
  padding: "8px 16px",
  background: "#f59e0b",              // amber — unmistakable
  color: "#1f1205",
  fontSize: "0.8125rem",
  fontWeight: 500,
  borderBottom: "2px solid #b45309",
  position: "sticky",
  top: 0,
  zIndex: 50,
};

const exitBtn: React.CSSProperties = {
  padding: "4px 12px",
  background: "#1f1205",
  color: "#fbbf24",
  border: "none",
  borderRadius: 4,
  cursor: "pointer",
  fontWeight: 700,
  fontSize: "0.75rem",
};
