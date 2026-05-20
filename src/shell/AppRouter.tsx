import { AdminPage, AuditPage, CaseDetailPage, CaseListPage, DashboardPage, ReportWorkspacePage } from "@/features";
import { ImpersonationBanner } from "@/components";
import AppShell from "./AppShell";
import {
  caseIdFromRoute,
  isAdminRoute,
  isAuditRoute,
  isCaseDetailRoute,
  isCaseListRoute,
  isReportDetailRoute,
  reportRouteIds,
  ROUTES,
} from "./routes";
import { useHashRoute } from "./useHashRoute";

/** Hash-routed page switch for the Launchpad shell. */
export default function AppRouter() {
  const route = useHashRoute();

  let page;
  if (isAdminRoute(route)) {
    page = <AdminPage />;
  } else if (isReportDetailRoute(route)) {
    // Must match BEFORE isCaseDetailRoute since both share the /cases/ prefix.
    const ids = reportRouteIds(route);
    page = ids
      ? <ReportWorkspacePage caseId={ids.caseId} reportId={ids.reportId} />
      : <CaseListPage />;
  } else if (isCaseDetailRoute(route)) {
    const id = caseIdFromRoute(route);
    page = id ? <CaseDetailPage caseId={id} /> : <CaseListPage />;
  } else if (isCaseListRoute(route)) {
    page = <CaseListPage />;
  } else if (isAuditRoute(route)) {
    page = <AuditPage />;
  } else if (route === ROUTES.dashboard) {
    page = <DashboardPage />;
  } else {
    page = (
      <div style={{ padding: "var(--space-lg)" }}>
        <h1>Not found</h1>
        <p className="text-secondary">No route matches <code>{route}</code>.</p>
      </div>
    );
  }

  return (
    <>
      <ImpersonationBanner />
      <AppShell route={route}>{page}</AppShell>
    </>
  );
}
