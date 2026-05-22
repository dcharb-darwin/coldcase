import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  discoveryPackageDownloadUrl,
  exportDiscoveryPackage,
  getCase,
  getDocumentText,
  getDocumentTextStatus,
  listConversations,
  listPromptSuggestions,
  listReportsForCase,
  registerDocument,
  sendMessage,
  uploadDocument,
  registerMedia,
  startConversation,
  type Case as CaseT,
  type Document,
  type DocumentTextStatus,
  type MediaInput,
  type Message,
  type Report,
  type TimelineEntry as TimelineEntryT,
  type TimelineEntrySuggestion,
} from "@/lib/api/coldcase";
import { caseKeys } from "../queryKeys";
import ChatPanel from "../components/ChatPanel";
import NotesPanel from "../components/NotesPanel";
import BriefTab from "../tabs/BriefTab";
import PeopleTab from "../tabs/PeopleTab";
import TimelineTab from "../tabs/TimelineTab";
import HypothesisTab from "../tabs/HypothesisTab";
import GraphTab from "../tabs/GraphTab";
import ChainTab from "../tabs/ChainTab";
import ReportDrawer from "../components/ReportDrawer";
import { CaseTagBar, TagChip } from "../components/TagChips";
import { parseHashQuery, reportRoute, ROUTES, setHashPath } from "@/shell/routes";
import { useHashRoute } from "@/shell/useHashRoute";
import { useShellChrome } from "@/shell/ShellChromeContext";

// NOTE: the "report" drawer kind was removed in Phase A · PR 3 — viewing /
// editing an existing report now happens at a dedicated route. The drawer
// retains the "promote" flow since that's a continuation from a chat message.
type DrawerState =
  | { kind: "closed" }
  | { kind: "promote"; sourceMessage: Message };

type CaseTab = "brief" | "evidence" | "people" | "timeline" | "hypothesis" | "graph" | "reports" | "chain" | "export";

const CASE_TABS: { id: CaseTab; label: string; hint: string }[] = [
  { id: "brief",      label: "Brief",      hint: "Overview" },
  { id: "evidence",   label: "Evidence",   hint: "Documents + media" },
  { id: "people",     label: "People",     hint: "Suspects · witnesses · victims" },
  { id: "timeline",   label: "Timeline",   hint: "Chronological case activity" },
  { id: "hypothesis", label: "Hypothesis", hint: "Brain dump → AI → investigation" },
  { id: "graph",      label: "Graph",      hint: "Visual neighborhood" },
  { id: "reports",    label: "Reports",    hint: "Drafts + signed" },
  { id: "chain",      label: "Chain",      hint: "Per-case audit (§13663(c))" },
  { id: "export",     label: "Export",     hint: "Discovery + evidence.com" },
];

interface CaseDetailPageProps {
  caseId: string;
}

export default function CaseDetailPage({ caseId }: CaseDetailPageProps) {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: caseKeys.detail(caseId),
    queryFn: () => getCase(caseId),
  });
  const { data: reports = [] } = useQuery({
    queryKey: caseKeys.reports(caseId),
    queryFn: () => listReportsForCase(caseId),
  });
  const { data: convs = [], isLoading: convsLoading, isFetching: convsFetching } = useQuery({
    queryKey: caseKeys.conversations(caseId),
    queryFn: () => listConversations(caseId),
  });

  const [drawer, setDrawer] = useState<DrawerState>({ kind: "closed" });
  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  const [highlightLine, setHighlightLine] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<CaseTab>("evidence");

  // Surface the case number in the breadcrumb so it reads "Cases / CC-2026-0001"
  // rather than the static "Cases / Case detail".
  const { setDetailLabel } = useShellChrome();
  useEffect(() => {
    if (data?.case.case_number) {
      setDetailLabel(data.case.case_number);
      return () => setDetailLabel(null);
    }
    return;
  }, [data?.case.case_number, setDetailLabel]);

  // Cross-route citation jump: ReportWorkspacePage forwards citation chip
  // clicks here as `?doc=<filename>&line=<n>`. Switch to the Evidence tab,
  // open the named document, flash the line, then clean the query so a
  // refresh doesn't keep re-firing.
  const route = useHashRoute();
  useEffect(() => {
    if (!data) return;
    const q = parseHashQuery(route);
    // ?tab=<id> — cross-tab navigation (used by the InferredMentions
    // "view on Brief tab" link). Honored independently of ?doc=&line=.
    if (q.tab && (CASE_TABS.some((t) => t.id === q.tab))) {
      setActiveTab(q.tab as CaseTab);
      setHashPath(`${ROUTES.casePrefix}${caseId}`);
      return;
    }
    if (!q.doc || !q.line) return;
    const target = data.documents.find((d) => d.original_filename === q.doc);
    if (!target) {
      setHashPath(`${ROUTES.casePrefix}${caseId}`);
      return;
    }
    setActiveTab("evidence");
    setActiveDocId(target.id);
    setHighlightLine(Number(q.line));
    setHashPath(`${ROUTES.casePrefix}${caseId}`);
  }, [route, data, caseId]);

  // Citation handler — invoked by clickable chips in chat messages and report
  // text. Switches to the cited document and highlights the cited line.
  const handleCitationClick = useCallback((filename: string, line: number) => {
    if (!data) return;
    const target = data.documents.find((d) => d.original_filename === filename);
    if (!target) return;
    setActiveTab("evidence");
    setActiveDocId(target.id);
    setHighlightLine(line);
  }, [data]);

  // Auto-select the first document when the case loads so the viewer pane is
  // never empty for a freshly-seeded demo case.
  useEffect(() => {
    if (!activeDocId && data && data.documents.length > 0) {
      setActiveDocId(data.documents[0]!.id);
    }
  }, [data?.documents.length, activeDocId, data]);

  // Auto-create a conversation if none exists yet so the chat panel +
  // prompt suggestions are immediately usable.
  //
  // The query starts with `data: undefined` then resolves to `[]` if there
  // are no conversations, OR to a non-empty array. Without the loading
  // guard, the effect fired during the initial render (when convs default
  // to `[]`) and again on every revisit, spawning a stampede of empty
  // "Case discussion" conversations. Wait until the query has resolved
  // (not loading, not fetching) and confirmed zero.
  const autoCreatedRef = useRef(false);
  useEffect(() => {
    if (!data) return;
    if (convsLoading || convsFetching) return;
    if (convs.length > 0) return;
    if (autoCreatedRef.current) return;
    autoCreatedRef.current = true;
    void startConversation(caseId, "Case discussion").then(() => {
      qc.invalidateQueries({ queryKey: caseKeys.conversations(caseId) });
    });
  }, [data?.case.id, convs.length, convsLoading, convsFetching, caseId, qc]);

  // The promote form fires a window event after a successful promote so we
  // can jump straight to the editor with the new draft.
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as { reportId: string };
      setHashPath(reportRoute(caseId, detail.reportId));
    };
    window.addEventListener("open-report", handler);
    return () => window.removeEventListener("open-report", handler);
  }, [caseId]);

  if (isLoading) return <div className="p-6 text-slate-500">Loading case…</div>;
  if (error) return <div className="p-6 text-red-700">{(error as Error).message}</div>;
  if (!data) return <div className="p-6 text-slate-500">Case not found.</div>;

  const { case: c, documents, media } = data;
  const activeDoc = documents.find((d) => d.id === activeDocId) ?? null;

  return (
    <div className="flex flex-col h-[calc(100vh-var(--shell-topbar-height,56px))]">
      <CaseHero
        c={c}
        docCount={documents.length}
        mediaCount={media.length}
        reportCount={reports.length}
        caseId={caseId}
      />

      <TabBar active={activeTab} onSelect={setActiveTab} />

      {/* Two columns: tab content (8) + persistent chat (4) */}
      <div className="flex-1 grid grid-cols-12 overflow-hidden">
        <section className="col-span-8 bg-white overflow-hidden border-r border-slate-200">
          {activeTab === "brief" && (
            <BriefTab c={c} documents={documents} media={media} reports={reports} />
          )}
          {activeTab === "evidence" && (
            <EvidenceTab
              caseId={caseId}
              documents={documents}
              media={media}
              activeDocId={activeDocId}
              setActiveDocId={setActiveDocId}
              activeDoc={activeDoc}
              highlightLine={highlightLine}
              onChanged={() => qc.invalidateQueries({ queryKey: caseKeys.detail(caseId) })}
            />
          )}
          {activeTab === "people" && (
            <PeopleTab caseId={caseId} />
          )}
          {activeTab === "timeline" && (
            <TimelineTab caseId={caseId} />
          )}
          {activeTab === "hypothesis" && (
            <HypothesisTab caseId={caseId} />
          )}
          {activeTab === "graph" && (
            <GraphTab caseId={caseId} />
          )}
          {activeTab === "reports" && (
            <ReportsTab
              reports={reports}
              onOpen={(rid) => setHashPath(reportRoute(caseId, rid))}
            />
          )}
          {activeTab === "chain" && (
            <ChainTab caseId={caseId} reports={reports} />
          )}
          {activeTab === "export" && (
            <CompliancePanel caseId={caseId} reports={reports} documents={documents} media={media} />
          )}
        </section>

        {/* Persistent chat */}
        <section className="col-span-4 bg-white overflow-hidden">
          <ChatPanel
            caseId={caseId}
            documents={documents}
            media={media}
            onPromote={(m) => setDrawer({ kind: "promote", sourceMessage: m })}
            onCitationClick={handleCitationClick}
          />
        </section>
      </div>

      <ReportDrawer
        caseId={caseId}
        state={drawer}
        onClose={() => setDrawer({ kind: "closed" })}
        onCitationClick={handleCitationClick}
      />
    </div>
  );
}

// ── Hero band + tab bar ─────────────────────────────────────────────────────

function CaseHero({
  c, docCount, mediaCount, reportCount, caseId,
}: {
  c: CaseT;
  docCount: number;
  mediaCount: number;
  reportCount: number;
  caseId: string;
}) {
  const stateColor: Record<string, string> = {
    open:     "bg-blue-50 text-blue-800 border-blue-200",
    active:   "bg-emerald-50 text-emerald-800 border-emerald-200",
    closed:   "bg-slate-100 text-slate-700 border-slate-300",
    reopened: "bg-amber-50 text-amber-800 border-amber-200",
  };
  const isDanger = c.classification === "homicide" || c.classification === "sexual_assault";
  const last = c.last_activity_at ? new Date(c.last_activity_at) : null;
  return (
    <div className="border-b border-slate-200 bg-white px-6 py-3 flex-shrink-0">
      {/* Title row + workflow CTA. Wraps on narrow widths so the title is
          never truncated by the action button. */}
      <div className="flex flex-col gap-2 md:flex-row md:items-baseline md:justify-between md:gap-4">
        <div className="min-w-0">
          <div className="text-[11px] text-slate-500 font-mono">
            {c.case_number}
            {c.external_id ? <span className="ml-2 text-slate-400">· {c.external_id}</span> : null}
          </div>
          <h1 className="text-xl font-semibold leading-tight truncate">{c.title}</h1>
        </div>
        <div className="shrink-0">
          <SelfReviewButton caseId={caseId} />
        </div>
      </div>

      {/* State band — semantic colors only used here for state */}
      <div className="flex flex-wrap gap-1.5 mt-2 items-center">
        <HeroChip
          tone={isDanger ? "danger" : "neutral"}
          label={c.classification.replace("_", " ")}
        />
        <HeroChip
          className={`border ${stateColor[c.status] ?? "bg-slate-100 text-slate-700"}`}
          label={c.status}
        />
        <HeroChip tone="neutral" label={`retention: ${c.retention_policy}`} />
        {c.date_of_incident ? (
          <HeroChip tone="neutral" label={`incident: ${c.date_of_incident}`} />
        ) : null}
        <HeroChip tone="neutral" label={`${docCount} docs · ${mediaCount} media · ${reportCount} reports`} />
        {last ? (
          <HeroChip tone="neutral" label={`last activity ${relativeTime(last)}`} />
        ) : null}
      </div>

      {c.description ? (
        <p className="text-sm text-slate-600 mt-2 max-w-4xl">{c.description}</p>
      ) : null}

      {/* Tag bar — system tags (computed) + user tags (picker-driven).
          System chips render with a lock icon and can't be removed. */}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {(c.system_tags ?? []).map((t) => <TagChip key={t.id} tag={t} />)}
        <CaseTagBar caseId={caseId} subjectKind="case" subjectId={c.id} />
      </div>
    </div>
  );
}

function HeroChip({
  label, tone = "neutral", className = "",
}: { label: string; tone?: "neutral" | "danger"; className?: string }) {
  const base = "inline-flex items-center px-2 py-0.5 rounded text-[11px] capitalize";
  const toneCls = tone === "danger"
    ? "bg-red-50 text-red-800 border border-red-200"
    : "bg-slate-100 text-slate-700";
  return <span className={`${base} ${className || toneCls}`}>{label}</span>;
}

function relativeTime(d: Date): string {
  const sec = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  if (sec < 86400 * 30) return `${Math.floor(sec / 86400)}d ago`;
  return d.toISOString().slice(0, 10);
}

function TabBar({ active, onSelect }: { active: CaseTab; onSelect: (t: CaseTab) => void }) {
  return (
    <div className="border-b border-slate-200 bg-slate-50 px-3 flex gap-0 overflow-x-auto flex-shrink-0">
      {CASE_TABS.map((t) => {
        const isActive = active === t.id;
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => onSelect(t.id)}
            className={
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors " +
              (isActive
                ? "border-blue-600 text-blue-700 bg-white"
                : "border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100")
            }
            title={t.hint}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

// ── Tab content ────────────────────────────────────────────────────────────

function EvidenceTab({
  caseId, documents, media, activeDocId, setActiveDocId, activeDoc, highlightLine, onChanged,
}: {
  caseId: string;
  documents: Document[];
  media: MediaInput[];
  activeDocId: string | null;
  setActiveDocId: (id: string | null) => void;
  activeDoc: Document | null;
  highlightLine: number | null;
  onChanged: () => void;
}) {
  return (
    <div className="grid grid-cols-8 h-full overflow-hidden">
      <aside className="col-span-3 border-r border-slate-200 bg-slate-50 overflow-y-auto">
        <SidebarSection title="Documents" count={documents.length}>
          <div className="flex flex-col gap-1.5">
            <UploadDocumentInline caseId={caseId} onDone={onChanged} />
            <RegisterDocumentInline caseId={caseId} onDone={onChanged} />
          </div>
          <ul className="space-y-1 mt-2">
            {documents.map((d) => (
              <li key={d.id}>
                <button
                  type="button"
                  onClick={() => setActiveDocId(d.id === activeDocId ? null : d.id)}
                  className={`w-full text-left text-xs px-2 py-1 rounded ${
                    activeDocId === d.id ? "bg-blue-100 text-blue-900" : "hover:bg-slate-100"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <span>📄</span>
                    <span className="font-medium truncate">{d.original_filename}</span>
                  </div>
                  <div className="flex items-center justify-between mt-0.5">
                    <span className="font-mono text-[10px] text-slate-500">{d.sha256.slice(0, 12)}…</span>
                    <ExtractionBadge caseId={caseId} documentId={d.id} />
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </SidebarSection>

        <SidebarSection title="Media" count={media.length}>
          <RegisterMediaInline caseId={caseId} onDone={onChanged} />
          <ul className="space-y-1 mt-2">
            {media.map((m: MediaInput) => (
              <li key={m.id} className="text-xs px-2 py-1 rounded hover:bg-slate-100">
                🎥 <span className="font-medium">{m.source_type}</span>
                <div className="text-[10px] text-slate-500">{m.duration_seconds}s</div>
              </li>
            ))}
          </ul>
        </SidebarSection>
      </aside>

      <section className="col-span-5 bg-white overflow-y-auto">
        {activeDoc ? (
          <DocumentViewer caseId={caseId} doc={activeDoc} highlightLine={highlightLine} />
        ) : (
          <DocumentEmpty />
        )}
      </section>
    </div>
  );
}

function ReportsTab({ reports, onOpen }: { reports: Report[]; onOpen: (rid: string) => void }) {
  if (reports.length === 0) {
    return (
      <div className="p-6 text-sm text-slate-500">
        No reports yet. In the chat panel on the right, ask the case a question — when you get an
        answer you want to keep, click the <strong>📌 Use as official report</strong> action on
        that assistant message to start a draft.
      </div>
    );
  }
  return (
    <div className="p-6 overflow-y-auto h-full">
      <h2 className="text-[15px] font-semibold text-slate-900 mb-3">
        Reports <span className="text-slate-500 font-normal">({reports.length})</span>
      </h2>
      <ul className="space-y-2 max-w-3xl">
        {reports.map((r) => (
          <li key={r.id}>
            <button
              type="button"
              onClick={() => onOpen(r.id)}
              className="w-full text-left p-3 border border-slate-200 rounded hover:border-blue-400 hover:bg-blue-50 transition-colors"
            >
              <div className="flex items-baseline justify-between gap-3">
                <div className="font-medium truncate">{r.title}</div>
                <ReportStatusChip status={r.status} />
              </div>
              <div className="text-[11px] text-slate-500 mt-1 flex flex-wrap gap-x-3">
                <span>{r.signed_at ? `signed ${new Date(r.signed_at).toLocaleString()}` : `created ${new Date(r.created_at ?? "").toLocaleDateString()}`}</span>
                {r.external_id ? <span className="font-mono">{r.external_id}</span> : null}
                {r.evidence_com_asset_id ? <span>evidence.com: {r.evidence_com_asset_id}</span> : null}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ReportStatusChip({ status }: { status: Report["status"] }) {
  const map: Record<Report["status"], string> = {
    draft:      "bg-amber-100 text-amber-800",
    signed:     "bg-emerald-100 text-emerald-800",
    exported:   "bg-blue-100 text-blue-800",
    superseded: "bg-slate-200 text-slate-700",
  };
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded ${map[status]}`}>
      {status}
    </span>
  );
}


function SidebarSection({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-slate-200 p-3">
      <div className="text-xs uppercase tracking-wide text-slate-500 mb-2 flex justify-between">
        <span>{title}</span>
        <span>{count}</span>
      </div>
      {children}
    </div>
  );
}

function CompliancePanel({
  caseId,
  reports,
  documents,
  media,
}: {
  caseId: string;
  reports: Report[];
  documents: Document[];
  media: MediaInput[];
}) {
  const [reason, setReason] = useState("");
  const [includeSourceBinaries, setIncludeSourceBinaries] = useState(false);
  const signed = reports.filter((r) => r.status === "signed" || r.status === "exported");

  const mut = useMutation({
    mutationFn: () => exportDiscoveryPackage(caseId, {
      reason,
      include_source_binaries: includeSourceBinaries,
    }),
  });

  return (
    <div className="p-6 overflow-y-auto h-full">
      <div className="max-w-3xl space-y-6">
        <header>
          <h2 className="text-[15px] font-semibold text-slate-900">
            Export
          </h2>
          <p className="text-sm text-slate-600 mt-1">
            Records-officer surface. Hand off this case to defense counsel, the DA, or the
            city attorney under §13663 / Brady disclosure.
          </p>
        </header>

        <section className="border border-slate-200 rounded p-4 bg-white">
          <h3 className="font-semibold mb-1">Discovery package</h3>
          <p className="text-sm text-slate-600 mb-3">
            Hash-pinned ZIP containing every signed report ({signed.length}) + its §13663(c)
            chain-of-custody PDF, plus pointer records for {documents.length} source
            document(s) and {media.length} media input(s).
          </p>
          <label className="block mb-2">
            <span className="text-xs text-slate-600">Reason (recorded in the audit event)</span>
            <input
              className="mt-1 w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
              placeholder="e.g. Defense discovery motion 24-CV-001234"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <label className="flex items-center gap-2 text-xs text-slate-700 mb-3">
            <input
              type="checkbox"
              checked={includeSourceBinaries}
              onChange={(e) => setIncludeSourceBinaries(e.target.checked)}
            />
            <span>
              Include source-document binaries in the ZIP
              <span className="text-slate-500"> (default off — customer storage is
                canonical; only enable when the recipient cannot pull from the customer's
                primary storage)</span>
            </span>
          </label>
          {mut.error ? (
            <div className="text-sm text-red-700 mb-2">{(mut.error as Error).message}</div>
          ) : null}
          {mut.data ? (
            <div className="mb-3 p-3 rounded border border-emerald-200 bg-emerald-50 text-emerald-900 text-sm">
              <div>
                ✓ Discovery package ready: {mut.data.file_count} files, {Math.round(mut.data.zip_size_bytes / 1024)} KB
              </div>
              <div className="font-mono text-xs mt-1">
                manifest_sha256: {mut.data.manifest_sha256.slice(0, 24)}…
              </div>
              <a
                href={discoveryPackageDownloadUrl(caseId, mut.data.zip_filename)}
                target="_blank"
                rel="noreferrer"
                className="inline-block mt-2 px-3 py-1 rounded bg-emerald-600 text-white text-xs"
              >
                Download {mut.data.zip_filename} ↗
              </a>
            </div>
          ) : null}
          <button
            type="button"
            disabled={mut.isPending || !reason.trim() || signed.length === 0}
            onClick={() => mut.mutate()}
            className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white disabled:opacity-50"
          >
            {mut.isPending ? "Assembling ZIP…" : "Export for discovery"}
          </button>
          {signed.length === 0 ? (
            <div className="mt-2 text-xs text-slate-500 italic">
              No signed reports yet — export is disabled until at least one official report
              is signed.
            </div>
          ) : null}
        </section>

        <section className="border border-slate-200 rounded p-4 bg-white">
          <h3 className="font-semibold mb-1">evidence.com</h3>
          <p className="text-sm text-slate-600">
            Per-report publish to evidence.com is planned for Phase B. Every signed report
            already carries the metadata evidence.com will need (external id, agency ORI,
            officer identity, content hash, AI program inventory) — see
            <code className="ml-1 text-xs">docs/design/workflow-and-ux.md §13</code>.
          </p>
        </section>
      </div>
    </div>
  );
}


function ExtractionBadge({ caseId, documentId }: { caseId: string; documentId: string }) {
  const { data } = useQuery({
    queryKey: ["doc-text-status", caseId, documentId],
    queryFn: () => getDocumentTextStatus(caseId, documentId),
    staleTime: 60_000,
  });
  if (!data) {
    return <span className="text-[10px] text-slate-400">…</span>;
  }
  const { method, non_ws_chars } = data;
  const palette: Record<DocumentTextStatus["method"], string> = {
    "text-layer": "bg-emerald-100 text-emerald-800",
    "ocr":        "bg-amber-100 text-amber-800",
    "plaintext":  "bg-slate-100 text-slate-700",
    "empty":      "bg-red-100 text-red-800",
    "error":      "bg-red-100 text-red-800",
  };
  const label: Record<DocumentTextStatus["method"], string> = {
    "text-layer": "text",
    "ocr":        "ocr",
    "plaintext":  "text",
    "empty":      "empty",
    "error":      "err",
  };
  return (
    <span
      className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${palette[method]}`}
      title={`Extraction: ${method} · ${non_ws_chars.toLocaleString()} non-ws chars · the AI can ${method === "empty" || method === "error" ? "NOT" : ""} see this doc`}
    >
      {label[method]} · {non_ws_chars >= 1000 ? `${Math.round(non_ws_chars / 1000)}k` : non_ws_chars}
    </span>
  );
}

function DocumentEmpty() {
  return (
    <div className="h-full flex items-center justify-center bg-slate-50">
      <div className="text-center max-w-sm px-6">
        <div className="mx-auto w-12 h-12 rounded-full bg-white border border-slate-200 flex items-center justify-center mb-3 text-slate-400">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <path d="M14 2v6h6" />
          </svg>
        </div>
        <h3 className="text-sm font-semibold text-slate-700">No document selected</h3>
        <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
          Pick a document on the left to read it, or use the chat panel on the right
          to ask the case a question. Citations in chat will jump you to the right line here.
        </p>
      </div>
    </div>
  );
}

function DocumentViewer({
  caseId,
  doc,
  highlightLine,
}: {
  caseId: string;
  doc: Document;
  highlightLine: number | null;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["doc-text", caseId, doc.id],
    queryFn: () => getDocumentText(caseId, doc.id),
  });
  const lineRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const [flashLine, setFlashLine] = useState<number | null>(null);

  useEffect(() => {
    if (!highlightLine || !data) return;
    const el = lineRefs.current[highlightLine];
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlashLine(highlightLine);
    const timeout = window.setTimeout(() => setFlashLine(null), 2400);
    return () => window.clearTimeout(timeout);
  }, [highlightLine, data]);

  const lines = data?.lines ?? [];

  return (
    <div className="p-6 h-full flex flex-col">
      <h2 className="font-semibold text-base">{doc.original_filename}</h2>
      <div className="text-[11px] text-slate-500 mt-1 space-y-0.5 flex-shrink-0">
        <div><strong>URI:</strong> <code className="text-slate-700">{doc.storage_uri}</code></div>
        <div className="font-mono"><strong>sha256:</strong> {doc.sha256.slice(0, 24)}…</div>
        <div>
          <strong>{doc.mime_type}</strong> · {doc.size_bytes} bytes · {doc.page_count} page(s) ·
          <span className="ml-1">{data?.line_count ?? 0} lines</span>
        </div>
      </div>
      {/* Per-document tag bar — reuses the same closed-vocabulary picker
          as the case hero, scoped to subject_kind=document. */}
      <div className="mt-2 flex-shrink-0">
        <CaseTagBar caseId={caseId} subjectKind="document" subjectId={doc.id} />
      </div>
      <div className="mt-3 flex-1 min-h-0 border border-slate-200 rounded bg-slate-50 overflow-auto">
        {isLoading ? (
          <div className="p-4 text-sm text-slate-500">Extracting text…</div>
        ) : error ? (
          <div className="p-4 text-sm text-red-700">{(error as Error).message}</div>
        ) : lines.length === 0 ? (
          <div className="p-4 text-sm text-slate-500">(no extractable text)</div>
        ) : (
          <div className="font-mono text-[12.5px] leading-relaxed">
            {lines.map((line, i) => {
              const n = i + 1;
              const isFlash = flashLine === n;
              return (
                <div
                  key={n}
                  ref={(el) => { lineRefs.current[n] = el; }}
                  className={
                    `flex gap-3 px-3 py-0.5 transition-colors duration-700 ` +
                    (isFlash ? "bg-yellow-200" : "hover:bg-slate-100")
                  }
                >
                  <span className="text-slate-400 select-none w-10 text-right shrink-0">{n}</span>
                  <span className="whitespace-pre-wrap break-words">{line || " "}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function UploadDocumentInline({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const m = useMutation({
    mutationFn: (file: File) => uploadDocument(caseId, file),
    onSuccess: () => {
      if (inputRef.current) inputRef.current.value = "";
      onDone();
    },
  });
  return (
    <div className="space-y-1">
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={m.isPending}
        className="text-xs text-blue-700 hover:underline disabled:opacity-50"
      >
        {m.isPending ? "Uploading…" : "+ Upload document"}
      </button>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) m.mutate(f);
        }}
      />
      {m.error ? <div className="text-[11px] text-red-700">{(m.error as Error).message}</div> : null}
    </div>
  );
}

function RegisterDocumentInline({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [uri, setUri] = useState("");
  const [name, setName] = useState("");
  const m = useMutation({
    mutationFn: () => registerDocument(caseId, { storage_uri: uri, original_filename: name || uri }),
    onSuccess: () => { setUri(""); setName(""); setOpen(false); onDone(); },
  });
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs text-blue-700 hover:underline"
      >
        + Register document
      </button>
    );
  }
  return (
    <div className="space-y-1.5">
      <input className="w-full border border-slate-300 rounded px-2 py-1 text-xs" placeholder="filename.pdf (under uploads/)" value={uri} onChange={(e) => setUri(e.target.value)} />
      <input className="w-full border border-slate-300 rounded px-2 py-1 text-xs" placeholder="Original filename" value={name} onChange={(e) => setName(e.target.value)} />
      {m.error ? <div className="text-[11px] text-red-700">{(m.error as Error).message}</div> : null}
      <div className="flex gap-1">
        <button type="button" onClick={() => m.mutate()} disabled={m.isPending || !uri.trim()} className="text-xs px-2 py-0.5 rounded bg-blue-600 text-white disabled:opacity-50">
          {m.isPending ? "…" : "Add"}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="text-xs px-2 py-0.5 rounded border border-slate-300">
          Cancel
        </button>
      </div>
    </div>
  );
}

function RegisterMediaInline({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [uri, setUri] = useState("");
  const [sourceType, setSourceType] = useState<MediaInput["source_type"]>("bodycam");
  const m = useMutation({
    mutationFn: () => registerMedia(caseId, {
      storage_uri: uri,
      source_type: sourceType,
      sha256: "0".repeat(64),
    }),
    onSuccess: () => { setUri(""); setOpen(false); onDone(); },
  });
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs text-blue-700 hover:underline"
      >
        + Register media (§13663(c)(2))
      </button>
    );
  }
  return (
    <div className="space-y-1.5">
      <input className="w-full border border-slate-300 rounded px-2 py-1 text-xs" placeholder="storage URI" value={uri} onChange={(e) => setUri(e.target.value)} />
      <select className="w-full border border-slate-300 rounded px-2 py-1 text-xs" value={sourceType} onChange={(e) => setSourceType(e.target.value as MediaInput["source_type"])}>
        {(["bodycam", "dashcam", "interview_audio", "interview_video", "call_recording", "other"] as const).map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
      {m.error ? <div className="text-[11px] text-red-700">{(m.error as Error).message}</div> : null}
      <div className="flex gap-1">
        <button type="button" onClick={() => m.mutate()} disabled={m.isPending || !uri.trim()} className="text-xs px-2 py-0.5 rounded bg-blue-600 text-white disabled:opacity-50">
          {m.isPending ? "…" : "Add"}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="text-xs px-2 py-0.5 rounded border border-slate-300">
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── Self-review of officer's own draft ──────────────────────────────────────
//
// One-button workflow: detective picks the file of their own draft narrative
// (Word export, PDF, etc.), we upload it through the existing artifact path,
// kick off a fresh conversation, send the `self_review` prompt scoped to JUST
// the uploaded doc (so other case documents don't muddy the gaps analysis),
// and surface the response in ChatPanel by dispatching an `open-conversation`
// CustomEvent — keeps ChatPanel's internal state encapsulated.
function SelfReviewButton({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<"" | "uploading" | "asking" | "error">("");
  const [error, setError] = useState("");

  const run = async (file: File) => {
    try {
      setError("");
      setPhase("uploading");
      const doc = await uploadDocument(caseId, file);
      qc.invalidateQueries({ queryKey: caseKeys.detail(caseId) });

      const promptCatalog = await listPromptSuggestions({
        case_id: caseId, document_id: doc.id,
      });
      const tmpl = promptCatalog.suggestions.find((s) => s.id === "self_review");
      if (!tmpl) throw new Error("self_review prompt not registered on server");

      setPhase("asking");
      const conv = await startConversation(caseId, `Self-review of ${doc.original_filename}`);
      await sendMessage(conv.id, {
        content: tmpl.rendered_prompt,
        in_context_document_ids: [doc.id],
      });
      qc.invalidateQueries({ queryKey: caseKeys.conversations(caseId) });
      window.dispatchEvent(
        new CustomEvent("open-conversation", { detail: { conversationId: conv.id } }),
      );
      setPhase("");
    } catch (e) {
      setError((e as Error).message);
      setPhase("error");
    }
  };

  const busy = phase === "uploading" || phase === "asking";
  return (
    <div className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        disabled={busy}
        className="px-3 py-1.5 text-xs rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 font-medium"
        title="Upload your own draft narrative (Word export, PDF) — Cold Case runs a defense-attorney/sergeant/DA gaps pass against it. The draft is treated as the document under review, not as a source."
      >
        {phase === "uploading" ? "Uploading your draft…"
          : phase === "asking" ? "Asking AI for gaps…"
          : "🪞 Review my draft for gaps"}
      </button>
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.txt,.md,.docx"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) run(f);
          // Reset so the same file can be re-selected on a follow-up review.
          if (fileRef.current) fileRef.current.value = "";
        }}
      />
      {error ? <span className="text-xs text-red-700">{error}</span> : null}
    </div>
  );
}
