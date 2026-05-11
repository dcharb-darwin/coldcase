import type { ReactNode } from "react";
import { useCallback, useMemo, useState } from "react";
import { usePermission } from "@/launchpad-admin";
import { breadcrumbTrail } from "./breadcrumbTrail";
import { isAdminRoute, isAuditRoute, isCaseDetailRoute, isCaseListRoute, ROUTES, setHashPath } from "./routes";
import { readNavCollapsedFromStorage, ShellChromeProvider, writeNavCollapsedToStorage } from "./ShellChromeContext";

type AppShellProps = {
  route: string;
  children: ReactNode;
};

function NavIconDashboard() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}

function NavIconAdmin() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M12 2l9 4v6c0 5-4 9-9 10-5-1-9-5-9-10V6l9-4z" />
    </svg>
  );
}

function NavIconCases() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  );
}

function NavIconAudit() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M9 12l2 2 4-4" />
      <path d="M21 12c0 5-4 9-9 9s-9-4-9-9 4-9 9-9c2 0 4 .6 5.5 1.7" />
    </svg>
  );
}

/**
 * Darwin Launchpad shell (P3): collapsible left rail + fixed top bar + breadcrumbs.
 * Add app-specific nav items inside the <nav> below as features land.
 */
export default function AppShell({ route, children }: AppShellProps) {
  return (
    <ShellChromeProvider>
      <AppShellChrome route={route}>{children}</AppShellChrome>
    </ShellChromeProvider>
  );
}

function AppShellChrome({ route, children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(readNavCollapsedFromStorage);
  const crumbs = useMemo(() => breadcrumbTrail(route, {}), [route]);
  const onDashboard = route === ROUTES.dashboard;
  const onCases = isCaseListRoute(route) || isCaseDetailRoute(route);
  const onAudit = isAuditRoute(route);
  const onAdmin = isAdminRoute(route);
  const canSeeAdmin = usePermission("admin.view");
  const navWidth = collapsed ? "var(--nav-width-collapsed)" : "var(--nav-width)";

  const go = useCallback((path: string) => setHashPath(path), []);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((c) => {
      const next = !c;
      writeNavCollapsedToStorage(next);
      return next;
    });
  }, []);

  return (
    <div className="app-shell">
      <aside
        className={`app-shell__sidebar${collapsed ? " app-shell__sidebar--collapsed" : ""}`}
        style={{ width: navWidth, minWidth: navWidth, transition: "width var(--transition-base), min-width var(--transition-base)" }}
      >
        <div className="app-shell__brand">
          {!collapsed ? (
            <>
              <span className="app-shell__brand-mark" aria-hidden>
                {"COL"}
              </span>
              <div className="app-shell__brand-text">
                <span className="app-shell__brand-title font-heading">{"Cold Case"}</span>
                <span className="app-shell__brand-sub text-muted">Launchpad</span>
              </div>
            </>
          ) : (
            <span className="app-shell__brand-mark" aria-hidden>
              {"COL"}
            </span>
          )}
        </div>
        <nav className="app-shell__nav" aria-label="Primary">
          <span className={`app-shell__nav-section ${collapsed ? "app-shell__nav-section--hidden" : ""}`}>Navigation</span>
          <button
            type="button"
            className={`app-shell__nav-item ${onDashboard ? "app-shell__nav-item--active" : ""}`}
            title="Dashboard"
            onClick={() => go(ROUTES.dashboard)}
          >
            <span className="app-shell__nav-icon"><NavIconDashboard /></span>
            {!collapsed ? <span>Dashboard</span> : null}
          </button>
          <button
            type="button"
            className={`app-shell__nav-item ${onCases ? "app-shell__nav-item--active" : ""}`}
            title="Cases"
            onClick={() => go(ROUTES.cases)}
          >
            <span className="app-shell__nav-icon"><NavIconCases /></span>
            {!collapsed ? <span>Cases</span> : null}
          </button>
          <button
            type="button"
            className={`app-shell__nav-item ${onAudit ? "app-shell__nav-item--active" : ""}`}
            title="Audit (§13663)"
            onClick={() => go(ROUTES.audit)}
          >
            <span className="app-shell__nav-icon"><NavIconAudit /></span>
            {!collapsed ? <span>Audit</span> : null}
          </button>
          {canSeeAdmin ? (
            <button
              type="button"
              className={`app-shell__nav-item ${onAdmin ? "app-shell__nav-item--active" : ""}`}
              title="Administration"
              onClick={() => go(ROUTES.admin)}
            >
              <span className="app-shell__nav-icon"><NavIconAdmin /></span>
              {!collapsed ? <span>Administration</span> : null}
            </button>
          ) : null}
        </nav>
        <div className="app-shell__sidebar-footer">
          <button
            type="button"
            id="btn-collapse-nav"
            className="app-shell__collapse-btn"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={toggleCollapsed}
          >
            <span aria-hidden>{collapsed ? "›" : "‹"}</span>
            {!collapsed ? <span>Collapse</span> : null}
          </button>
        </div>
      </aside>
      <div className="app-shell__body">
        <header className="app-shell__topbar">
          <div className="app-shell__breadcrumbs" aria-label="Breadcrumb">
            {crumbs.map((c, i) => (
              <span key={`${c.label}-${i}`} className="app-shell__crumb">
                {i > 0 ? <span className="app-shell__crumb-sep" aria-hidden>/</span> : null}
                {c.path ? (
                  <button type="button" className="app-shell__crumb-link" onClick={() => go(c.path!)}>
                    {c.label}
                  </button>
                ) : (
                  <span className="app-shell__crumb-current">{c.label}</span>
                )}
              </span>
            ))}
          </div>
          <div className="app-shell__topbar-actions">
            <span className="app-shell__avatar" title="Account">{"COL"}</span>
          </div>
        </header>
        <main className="app-shell__main">{children}</main>
      </div>
    </div>
  );
}
