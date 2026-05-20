import { ROUTES, setHashPath } from "@/shell/routes";
import { ReportWorkspace } from "../components/ReportDrawer";

/**
 * Phase A · PR 3 — report workspace as a full route at
 * `#/cases/:caseId/reports/:reportId`.
 *
 * Replaces the prior drawer-shaped report editor with a real page. The
 * promote flow stays in the drawer (it's a continuation from a chat
 * message — a route would feel like a redirect mid-thought), but the
 * edit/sign/export flow is a workspace and earns its own URL.
 *
 * Citation chip clicks bounce back to the case detail with `?doc=…&line=…`
 * query params; the case page parses those on mount and jumps straight to
 * the cited line in the Evidence tab.
 */
export default function ReportWorkspacePage({
  caseId, reportId,
}: { caseId: string; reportId: string }) {
  const backToCase = () => setHashPath(`${ROUTES.casePrefix}${caseId}`);
  const jumpToCitation = (filename: string, line: number) => {
    const params = new URLSearchParams({ doc: filename, line: String(line) });
    setHashPath(`${ROUTES.casePrefix}${caseId}?${params.toString()}`);
  };
  return (
    <div className="h-[calc(100vh-var(--shell-topbar-height,56px))] bg-slate-100">
      <ReportWorkspace
        caseId={caseId}
        reportId={reportId}
        onClose={backToCase}
        onCitationClick={jumpToCitation}
      />
    </div>
  );
}
