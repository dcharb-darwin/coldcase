import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  discoveryPackageDownloadUrl,
  exportDiscoveryPackage,
  getCase,
  getDocumentText,
  getDocumentTextStatus,
  assignTag,
  createNote,
  createTimelineEntry,
  deleteTimelineEntry,
  getAuditChainReport,
  getCaseConnections,
  getPersonNetwork,
  getReportChain,
  getSimilarCases,
  listAuditEvents,
  listConversations,
  listPromptSuggestions,
  listReportsForCase,
  listTimelineEntries,
  suggestCaseTags,
  suggestNextSteps,
  suggestTimelineEntries,
  registerDocument,
  sendMessage,
  uploadDocument,
  registerMedia,
  startConversation,
  type AuditEvent,
  type Case as CaseT,
  type Document,
  type DocumentTextStatus,
  type MediaInput,
  type Message,
  type NextStepSuggestion,
  type ConnectionNode,
  type RelatedPerson,
  type Report,
  type TagSuggestion,
  type TimelineEntry as TimelineEntryT,
  type TimelineEntrySuggestion,
} from "@/lib/api/coldcase";
import { caseKeys } from "../queryKeys";
import ChatPanel from "../components/ChatPanel";
import NotesPanel from "../components/NotesPanel";
import PeopleTab from "../tabs/PeopleTab";
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

type CaseTab = "brief" | "evidence" | "people" | "timeline" | "reports" | "chain" | "export";

const CASE_TABS: { id: CaseTab; label: string; hint: string }[] = [
  { id: "brief",    label: "Brief",    hint: "Overview" },
  { id: "evidence", label: "Evidence", hint: "Documents + media" },
  { id: "people",   label: "People",   hint: "Suspects · witnesses · victims" },
  { id: "timeline", label: "Timeline", hint: "Chronological case activity" },
  { id: "reports",  label: "Reports",  hint: "Drafts + signed" },
  { id: "chain",    label: "Chain",    hint: "Per-case audit (§13663(c))" },
  { id: "export",   label: "Export",   hint: "Discovery + evidence.com" },
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

function BriefTab({
  c, documents, media, reports,
}: { c: CaseT; documents: Document[]; media: MediaInput[]; reports: Report[] }) {
  const signedReports = reports.filter((r) => r.status === "signed" || r.status === "exported");
  const draftReports = reports.filter((r) => r.status === "draft");
  const lastSigned = signedReports
    .map((r) => r.signed_at)
    .filter(Boolean)
    .sort()
    .at(-1) ?? null;
  const ocrDocs = documents.length; // proxy until extraction status is bulk-fetchable

  // "Next step" hints. Ordered by escalating need; the first matching item
  // is what the detective should do next.
  const nextSteps: string[] = [];
  if (documents.length === 0) nextSteps.push("Upload or register your source documents in the Evidence tab.");
  if (documents.length > 0 && reports.length === 0) nextSteps.push("Ask the case a question in the chat panel and promote a useful answer to a report.");
  if (draftReports.length > 0) nextSteps.push(`Sign the ${draftReports.length} pending draft report${draftReports.length === 1 ? "" : "s"} in the Reports tab.`);
  if (!c.date_of_incident) nextSteps.push("Set the incident date — it's required for evidence.com export.");

  const userTags = c.tags ?? [];
  const sysTags = c.system_tags ?? [];

  return (
    <div className="p-6 overflow-y-auto h-full">
      <div className="max-w-4xl space-y-6">
        {/* Status snapshot — three stat cards. Anchors the page visually. */}
        <section>
          <div className="grid grid-cols-3 gap-3">
            <StatCard label="Documents" value={documents.length} hint={`${media.length} media`} />
            <StatCard
              label="Reports"
              value={reports.length}
              hint={`${signedReports.length} signed · ${draftReports.length} draft`}
              tone={signedReports.length > 0 ? "good" : draftReports.length > 0 ? "warn" : "muted"}
            />
            <StatCard
              label="AI exposure"
              value={ocrDocs > 0 || reports.length > 0 ? "Yes" : "—"}
              hint={
                reports.length > 0
                  ? `${reports.length} AI-assisted report${reports.length === 1 ? "" : "s"} on file`
                  : "No AI-assisted artifacts yet"
              }
              tone={reports.length > 0 ? "warn" : "muted"}
            />
          </div>
        </section>

        {/* Two layers of "what's next":
              - amber banner = rule-based mechanical hints (set incident date, sign drafts)
              - AI suggester = state-aware investigative steps grounded in the case docs */}
        {nextSteps.length > 0 ? (
          <section className="border border-amber-200 bg-amber-50/60 rounded p-3">
            <div className="text-[12px] font-semibold text-amber-900 mb-1">Suggested next step</div>
            <ul className="text-sm text-amber-900 space-y-1">
              {nextSteps.slice(0, 2).map((s) => (
                <li key={s} className="flex gap-2"><span>→</span><span>{s}</span></li>
              ))}
            </ul>
          </section>
        ) : null}

        <NextStepSuggester caseId={c.id} />

        {/* Key dates — vertical timeline of meaningful moments. */}
        <section>
          <h2 className="text-[15px] font-semibold text-slate-900 mb-3">Key dates</h2>
          <ol className="border-l-2 border-slate-200 pl-4 space-y-2.5 text-sm">
            <DateRow label="Incident occurred" value={c.date_of_incident} hint="§13663 incident_date" />
            <DateRow label="Case opened" value={c.created_at} />
            <DateRow label="Latest report signed" value={lastSigned} tone="good" />
            <DateRow label="Case closed" value={c.closed_at} tone="muted" />
          </ol>
        </section>

        {/* Investigators */}
        <section>
          <h2 className="text-[15px] font-semibold text-slate-900 mb-3">Investigators</h2>
          <div className="border border-slate-200 rounded p-3 text-sm">
            <div className="flex items-baseline gap-2">
              <span className="text-slate-500 text-xs">Primary</span>
              <span className="font-mono text-xs">{c.primary_investigator_id}</span>
            </div>
            {c.co_investigator_ids.length > 0 ? (
              <div className="mt-1.5">
                <span className="text-slate-500 text-xs">Co-investigators</span>
                <ul className="mt-0.5 text-xs font-mono text-slate-700">
                  {c.co_investigator_ids.map((id) => <li key={id}>{id}</li>)}
                </ul>
              </div>
            ) : null}
          </div>
        </section>

        <CaseConnectionsPanel caseId={c.id} />

        <SimilarCasesPanel caseId={c.id} />

        {/* Tags — grouped (detective-applied + server-derived) with an
            inline AI suggestion affordance. */}
        <section>
          <h2 className="text-[15px] font-semibold text-slate-900 mb-3">Tags</h2>
          <div className="space-y-3">
            {userTags.length > 0 ? (
              <div>
                <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Detective-applied</div>
                <div className="flex flex-wrap gap-1.5">
                  {userTags.map((t) => <TagChip key={t.id} tag={t} />)}
                </div>
              </div>
            ) : null}
            {sysTags.length > 0 ? (
              <div>
                <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Server-derived</div>
                <div className="flex flex-wrap gap-1.5">
                  {sysTags.map((t) => <TagChip key={t.id} tag={t} />)}
                </div>
              </div>
            ) : null}
            <TagSuggestions caseId={c.id} />
          </div>
        </section>

        {/* Detective scratch — freeform notes that don't enter the §13663
            chain or any export. Separate from the closed-vocab tag set. */}
        <section className="border border-slate-200 rounded p-3 bg-slate-50/30">
          <NotesPanel caseId={c.id} subjectKind="case" subjectId={c.id} />
        </section>

        {/* Identifiers — for evidence.com / records management exports. */}
        <section>
          <h2 className="text-[15px] font-semibold text-slate-900 mb-3">Identifiers</h2>
          <dl className="grid grid-cols-3 gap-x-4 gap-y-2 text-sm">
            <dt className="text-slate-500">Case number</dt>
            <dd className="col-span-2 font-mono">{c.case_number}</dd>
            <dt className="text-slate-500">External id</dt>
            <dd className="col-span-2 font-mono text-xs break-all">{c.external_id || "—"}</dd>
            <dt className="text-slate-500">Agency ORI</dt>
            <dd className="col-span-2 font-mono">{c.agency_ori_snapshot || "—"}</dd>
            <dt className="text-slate-500">Retention</dt>
            <dd className="col-span-2">{c.retention_policy.replace(/_/g, " ")}</dd>
          </dl>
        </section>

        {c.description ? (
          <section>
            <h2 className="text-[15px] font-semibold text-slate-900 mb-3">Description</h2>
            <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{c.description}</p>
          </section>
        ) : null}
      </div>
    </div>
  );
}

function TagSuggestions({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  // Lazy: the LLM call is paid + slow, so don't auto-fire. Show a CTA;
  // the detective triggers the suggestion explicitly. Result is cached
  // by react-query so toggling tabs doesn't re-spend.
  const [run, setRun] = useState(false);
  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["tag-suggestions", caseId],
    queryFn: () => suggestCaseTags(caseId),
    enabled: run,
    staleTime: 5 * 60_000,
  });

  // Dismissed slugs disappear locally until refetch. Keeps the picker
  // from showing the same rejected suggestion over and over while the
  // query is still cached.
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  // AI accept threads the model id + rationale into the assignment so the
  // chain records "this tag came from an LLM proposal that the officer
  // explicitly accepted" — not "officer applied this manually".
  const acceptMut = useMutation({
    mutationFn: (s: TagSuggestion) => assignTag(s.tag.id, "case", caseId, {
      source: "ai_suggested",
      suggested_by_model: data?.model ?? "",
      suggested_rationale: s.rationale,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: caseKeys.tags(caseId) });
      qc.invalidateQueries({ queryKey: caseKeys.detail(caseId) });
    },
  });

  const visible = (data?.suggestions ?? []).filter((s) => !dismissed.has(s.tag.slug));

  return (
    <div className="border border-slate-200 rounded p-3 bg-slate-50/40">
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <div>
          <div className="text-[12px] font-semibold text-slate-900">Suggest tags with AI</div>
          <div className="text-[11px] text-slate-500">
            Read the case docs and propose tags from the agency vocabulary.
            You accept each suggestion individually.
          </div>
        </div>
        <button
          type="button"
          onClick={() => { setRun(true); setDismissed(new Set()); refetch(); }}
          disabled={isFetching}
          className="px-2.5 py-1 text-xs rounded border border-blue-300 bg-white text-blue-800 hover:bg-blue-50 disabled:opacity-50 shrink-0"
        >
          {isFetching ? "Reading docs…" : run ? "Refresh" : "Suggest"}
        </button>
      </div>

      {error ? <div className="text-xs text-red-700">{(error as Error).message}</div> : null}
      {data?.reason ? <div className="text-xs text-slate-500 italic">{data.reason}</div> : null}

      {run && !isFetching && visible.length === 0 && !error ? (
        <div className="text-xs text-slate-500 italic">
          {data?.suggestions.length
            ? "All suggestions dismissed."
            : "No suggestions returned."}
        </div>
      ) : null}

      {visible.length > 0 ? (
        <ul className="space-y-1.5 mt-1">
          {visible.map((s: TagSuggestion) => {
            const accepted = acceptMut.isSuccess && acceptMut.variables?.tag.id === s.tag.id;
            return (
              <li
                key={s.tag.slug}
                className="flex items-start gap-2 p-2 bg-white border border-slate-200 rounded"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <TagChip tag={s.tag} />
                  </div>
                  <div className="text-[11px] text-slate-600 mt-1 leading-snug">{s.rationale}</div>
                </div>
                <div className="flex flex-col gap-1 shrink-0">
                  <button
                    type="button"
                    disabled={accepted || acceptMut.isPending}
                    onClick={() => acceptMut.mutate(s)}
                    className="px-2 py-0.5 text-[11px] rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {accepted ? "Added ✓" : "Accept"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setDismissed((p) => new Set(p).add(s.tag.slug))}
                    className="px-2 py-0.5 text-[11px] rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
                  >
                    Dismiss
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

function StatCard({
  label, value, hint, tone = "muted",
}: { label: string; value: number | string; hint?: string; tone?: "good" | "warn" | "muted" }) {
  const toneCls = tone === "good"
    ? "border-emerald-200 bg-emerald-50/40"
    : tone === "warn"
      ? "border-amber-200 bg-amber-50/40"
      : "border-slate-200 bg-white";
  return (
    <div className={`border rounded p-3 ${toneCls}`}>
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-2xl font-semibold text-slate-900 leading-tight mt-0.5">{value}</div>
      {hint ? <div className="text-[11px] text-slate-500 mt-1">{hint}</div> : null}
    </div>
  );
}

function DateRow({
  label, value, hint, tone = "default",
}: { label: string; value: string | null | undefined; hint?: string; tone?: "default" | "good" | "muted" }) {
  const missing = !value;
  const dotCls = missing
    ? "bg-slate-200"
    : tone === "good"
      ? "bg-emerald-500"
      : tone === "muted"
        ? "bg-slate-400"
        : "bg-blue-500";
  const formatted = value ? new Date(value).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: value.length > 10 ? "numeric" : undefined,
    minute: value.length > 10 ? "2-digit" : undefined,
  }) : null;
  return (
    <li className="relative">
      <span className={`absolute -left-[22px] top-1.5 w-3 h-3 rounded-full ring-2 ring-white ${dotCls}`} />
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-slate-700">{label}</span>
        <span className={missing ? "text-slate-400 italic text-xs" : "text-slate-900"}>
          {formatted ?? "not yet"}
        </span>
      </div>
      {hint ? <div className="text-[10px] text-slate-400">{hint}</div> : null}
    </li>
  );
}

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

// Category palette — semantic colors only used for the small category chip
// next to each suggestion. Investigative actions vs research vs legal etc.
const NEXT_STEP_CATEGORY_CLS: Record<string, string> = {
  interview:     "bg-blue-50 text-blue-800 border-blue-200",
  evidence:      "bg-emerald-50 text-emerald-800 border-emerald-200",
  legal:         "bg-red-50 text-red-800 border-red-200",
  documentation: "bg-amber-50 text-amber-800 border-amber-200",
  research:      "bg-indigo-50 text-indigo-800 border-indigo-200",
  other:         "bg-slate-100 text-slate-700 border-slate-300",
};

function NextStepSuggester({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const [run, setRun] = useState(false);
  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["next-step-suggestions", caseId],
    queryFn: () => suggestNextSteps(caseId),
    enabled: run,
    staleTime: 5 * 60_000,
  });
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  // Accepting a step pins it into Notes so it lives somewhere actionable.
  // Category + rationale go into the body so the audit trail of the
  // working memory is intact.
  const acceptMut = useMutation({
    mutationFn: (s: NextStepSuggestion) => createNote(caseId, {
      subject_kind: "case", subject_id: caseId,
      body: `[${s.category}] ${s.step}\n\nRationale: ${s.rationale}`,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case-notes", caseId] });
    },
  });

  const visible = (data?.suggestions ?? []).filter((s) => !dismissed.has(s.step));

  return (
    <section className="border border-indigo-200 bg-indigo-50/30 rounded p-3">
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <div>
          <h3 className="text-[12px] font-semibold text-slate-900">Investigative steps with AI</h3>
          <div className="text-[11px] text-slate-500">
            State-aware: reads the documents, people, reports, and timeline
            to propose concrete next moves. Accept saves the step as a note.
          </div>
        </div>
        <button
          type="button"
          onClick={() => { setRun(true); setDismissed(new Set()); refetch(); }}
          disabled={isFetching}
          className="px-2.5 py-1 text-xs rounded border border-indigo-300 bg-white text-indigo-800 hover:bg-indigo-50 disabled:opacity-50 shrink-0"
        >
          {isFetching ? "Thinking…" : run ? "Refresh" : "Suggest"}
        </button>
      </div>

      {error ? <div className="text-xs text-red-700">{(error as Error).message}</div> : null}
      {data?.reason ? <div className="text-xs text-slate-500 italic">{data.reason}</div> : null}

      {run && !isFetching && visible.length === 0 && !error && !data?.reason ? (
        <div className="text-xs text-slate-500 italic">
          {data?.suggestions.length ? "All suggestions handled." : "No suggestions returned."}
        </div>
      ) : null}

      {visible.length > 0 ? (
        <ul className="space-y-1.5 mt-1">
          {visible.map((s) => {
            const accepted = acceptMut.isSuccess && acceptMut.variables?.step === s.step;
            const catCls = NEXT_STEP_CATEGORY_CLS[s.category] ?? NEXT_STEP_CATEGORY_CLS.other!;
            return (
              <li
                key={s.step}
                className="flex items-start gap-2 p-2 bg-white border border-slate-200 rounded"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-start gap-2">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[10px] capitalize shrink-0 ${catCls}`}>
                      {s.category}
                    </span>
                    <span className="text-sm text-slate-900">{s.step}</span>
                  </div>
                  {s.rationale ? (
                    <div className="text-[11px] text-slate-600 italic mt-1 leading-snug">
                      {s.rationale}
                    </div>
                  ) : null}
                </div>
                <div className="flex flex-col gap-1 shrink-0">
                  <button
                    type="button"
                    disabled={accepted || acceptMut.isPending}
                    onClick={() => acceptMut.mutate(s)}
                    className="px-2 py-0.5 text-[11px] rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                    title="Save to Notes as a working scratch item"
                  >
                    {accepted ? "Saved ✓" : "Pin to notes"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setDismissed((p) => new Set(p).add(s.step))}
                    className="px-2 py-0.5 text-[11px] rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
                  >
                    Dismiss
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}

function SimilarCasesPanel({ caseId }: { caseId: string }) {
  // Tag-based Jaccard similarity. Quiet by default — only renders when
  // there's a non-zero overlap. Goes next to Connections because both
  // panels answer "what other cases should I look at?" — one via people,
  // the other via shared classification work.
  const { data, isLoading, error } = useQuery({
    queryKey: ["similar-cases", caseId],
    queryFn: () => getSimilarCases(caseId),
    staleTime: 60_000,
  });
  if (isLoading || error || !data || data.similar.length === 0) return null;

  return (
    <section>
      <div className="flex items-baseline justify-between mb-2">
        <h2 className="text-[15px] font-semibold text-slate-900">Similar cases</h2>
        <span className="text-[11px] text-slate-500">
          {data.similar.length} match{data.similar.length === 1 ? "" : "es"} · ranked by shared tags
        </span>
      </div>
      <ul className="space-y-1.5">
        {data.similar.map((c) => {
          const isDanger = c.case_classification === "homicide"
            || c.case_classification === "sexual_assault";
          return (
            <li key={c.case_id}>
              <button
                type="button"
                onClick={() => setHashPath(`${ROUTES.casePrefix}${c.case_id}`)}
                className="w-full text-left border border-slate-200 rounded p-2.5 bg-white hover:border-blue-400 hover:bg-blue-50/40"
              >
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-xs text-slate-700">{c.case_number}</span>
                  <span className="text-sm text-slate-900 truncate flex-1">{c.case_title}</span>
                  <span className={
                    "text-[11px] capitalize " +
                    (isDanger ? "text-red-700 font-medium" : "text-slate-500")
                  }>
                    {c.case_classification.replace("_", " ")}
                  </span>
                  <span className="text-[11px] font-mono text-slate-500">
                    {Math.round(c.score * 100)}%
                  </span>
                </div>
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {c.shared_tag_labels.map((lbl) => (
                    <span
                      key={lbl}
                      className="inline-flex items-center px-1.5 py-0.5 rounded-full border border-slate-200 bg-slate-50 text-slate-700 text-[10px]"
                    >
                      <span className="opacity-60 mr-0.5">#</span>{lbl}
                    </span>
                  ))}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function CaseConnectionsPanel({ caseId }: { caseId: string }) {
  // Derived graph: shows every person on this case + which other cases
  // they appear on. Not a fancy node-link visualization yet — that lands
  // when there's enough cross-case data to make it pay off. For now, a
  // structured list with click-through to the connected cases.
  const { data, isLoading, error } = useQuery({
    queryKey: ["case-connections", caseId],
    queryFn: () => getCaseConnections(caseId),
    staleTime: 60_000,
  });

  if (isLoading || error || !data) return null;

  // Group cross-case edges by source person.
  const otherCasesById = new Map(
    data.nodes
      .filter((n) => n.kind === "case" && n.id !== `case:${caseId}`)
      .map((n) => [n.id, n]),
  );
  const personRows = data.nodes
    .filter((n) => n.kind === "person")
    .map((p) => {
      const targets = data.edges
        .filter((e) => e.from === p.id && e.kind === "appears_on_other_case")
        .map((e) => otherCasesById.get(e.to))
        .filter((c): c is NonNullable<typeof c> => Boolean(c));
      return { person: p, targets };
    });

  // Only render the section if there's something to show.
  if (personRows.length === 0) return null;

  const hasAnyCrossCase = personRows.some((r) => r.targets.length > 0);

  return (
    <section>
      <div className="flex items-baseline justify-between mb-2">
        <h2 className="text-[15px] font-semibold text-slate-900">Connections</h2>
        <span className="text-[11px] text-slate-500">
          {data.stats.persons_on_case} people · {data.stats.connected_cases} connected case
          {data.stats.connected_cases === 1 ? "" : "s"}
        </span>
      </div>
      {!hasAnyCrossCase ? (
        <div className="text-xs text-slate-500 italic">
          No cross-case overlap yet. As people are added to other cases,
          their connections will appear here automatically.
        </div>
      ) : (
        <ul className="space-y-2">
          {personRows
            .filter((r) => r.targets.length > 0)
            .map(({ person, targets }) => (
              <ConnectionRow
                key={person.id}
                caseId={caseId}
                person={person}
                targets={targets}
              />
            ))}
        </ul>
      )}
    </section>
  );
}

function ConnectionRow({
  caseId, person, targets,
}: {
  caseId: string;
  person: ConnectionNode;
  targets: ConnectionNode[];
}) {
  // Two-hop expand. The fetch is gated on user click so we don't spend
  // a network query per person at panel-mount time. Result lives in
  // react-query so closing/reopening is free.
  const [expanded, setExpanded] = useState(false);
  const { data: network, isFetching: networkLoading } = useQuery({
    queryKey: ["person-network", person.name, caseId],
    queryFn: () => getPersonNetwork(person.name ?? "", { excludeCaseId: caseId }),
    enabled: expanded && Boolean(person.name),
    staleTime: 60_000,
  });

  // Group co-occurring people by the case where they share with the focal
  // person. The detective reads it as "on case X, James shows up with
  // Jane, John, …".
  const grouped = useMemo(() => {
    if (!network) return [] as { caseId: string; caseNumber: string; persons: RelatedPerson[] }[];
    const m = new Map<string, { caseId: string; caseNumber: string; persons: RelatedPerson[] }>();
    for (const r of network.related_persons) {
      const existing = m.get(r.on_case_id);
      if (existing) {
        existing.persons.push(r);
      } else {
        m.set(r.on_case_id, { caseId: r.on_case_id, caseNumber: r.on_case_number, persons: [r] });
      }
    }
    return [...m.values()];
  }, [network]);

  return (
    <li className="border border-slate-200 rounded p-2.5 bg-white">
      <div className="flex items-baseline gap-2">
        <span className="font-medium text-slate-900">{person.name}</span>
        <span className="text-[11px] text-slate-500 capitalize">
          ({person.role?.replace("_", " ")})
        </span>
        {person.ai_sourced ? (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded-full border border-purple-200 bg-purple-50 text-purple-800 text-[10px] uppercase tracking-wide font-medium">
            AI
          </span>
        ) : null}
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="ml-auto text-[11px] text-purple-700 hover:underline"
          title={expanded ? "Hide who else appears with this person" : "Show who else appears with this person on connected cases"}
        >
          {expanded ? "− network" : "+ network"}
        </button>
      </div>

      <ul className="mt-1.5 space-y-1">
        {targets.map((c) => (
          <li key={c.id}>
            <button
              type="button"
              onClick={() => setHashPath(`${ROUTES.casePrefix}${c.case_id}`)}
              className="w-full text-left flex items-baseline gap-2 px-2 py-1 rounded hover:bg-slate-50"
            >
              <span className="text-purple-700">↗</span>
              <span className="font-mono text-xs text-slate-700">{c.case_number}</span>
              <span className="text-sm text-slate-900 truncate flex-1">{c.case_title}</span>
              {c.case_classification === "homicide" || c.case_classification === "sexual_assault" ? (
                <span className="text-[11px] text-red-700 font-medium capitalize">
                  {c.case_classification?.replace("_", " ")}
                </span>
              ) : (
                <span className="text-[11px] text-slate-500 capitalize">
                  {c.case_classification?.replace("_", " ")}
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>

      {expanded ? (
        <div className="mt-2 ml-4 pl-3 border-l-2 border-purple-200">
          {networkLoading ? (
            <div className="text-[11px] text-slate-500 italic">Loading network…</div>
          ) : !network || grouped.length === 0 ? (
            <div className="text-[11px] text-slate-500 italic">
              No other people on the connected case
              {targets.length === 1 ? "" : "s"}.
            </div>
          ) : (
            grouped.map((g) => (
              <div key={g.caseId} className="mb-1.5 last:mb-0">
                <div className="text-[11px] text-slate-500">
                  Co-occurring on{" "}
                  <button
                    type="button"
                    onClick={() => setHashPath(`${ROUTES.casePrefix}${g.caseId}`)}
                    className="font-mono text-slate-700 hover:underline"
                  >
                    {g.caseNumber}
                  </button>:
                </div>
                <ul className="ml-2 mt-0.5 space-y-0.5">
                  {g.persons.map((rp: RelatedPerson, i: number) => (
                    <li key={`${rp.name}-${i}`} className="text-xs text-slate-700">
                      <span className="text-slate-900">{rp.name}</span>
                      <span className="text-[11px] text-slate-500 ml-1 capitalize">
                        ({rp.role.replace("_", " ")})
                      </span>
                      {rp.descriptor ? (
                        <span className="text-[11px] text-slate-500 ml-1">· {rp.descriptor}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </div>
      ) : null}
    </li>
  );
}

function TimelineTab({ caseId }: { caseId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["case-timeline", caseId],
    queryFn: () => listAuditEvents({ case_id: caseId, limit: 200 }),
    staleTime: 10_000,
  });

  const events = data?.events ?? [];

  // Group by yyyy-mm-dd (local). Newest day first; within a day, newest first.
  const grouped = useMemo(() => {
    const byDay = new Map<string, AuditEvent[]>();
    for (const e of events) {
      const day = e.timestamp ? new Date(e.timestamp).toISOString().slice(0, 10) : "unknown";
      byDay.set(day, [...(byDay.get(day) ?? []), e]);
    }
    return [...byDay.entries()].sort(([a], [b]) => b.localeCompare(a));
  }, [events]);

  if (isLoading) return <div className="p-6 text-sm text-slate-500">Loading timeline…</div>;
  if (error) return <div className="p-6 text-sm text-red-700">{(error as Error).message}</div>;
  if (events.length === 0) {
    return (
      <div className="p-6 text-sm text-slate-500 max-w-3xl">
        No activity on this case yet. Events appear here as documents are registered,
        chat messages are sent, and reports are signed.
      </div>
    );
  }

  return (
    <div className="p-6 overflow-y-auto h-full">
      <div className="max-w-3xl space-y-6">
        <CaseEventsSection caseId={caseId} />

        <section>
          <h2 className="text-[15px] font-semibold text-slate-900 mb-1">Activity log</h2>
          <p className="text-xs text-slate-500 mb-4">
            Every action on this case, chronologically. {events.length} event{events.length === 1 ? "" : "s"}.
          </p>
          {grouped.map(([day, list]) => (
            <section key={day} className="mb-6">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2 sticky top-0 bg-white py-1">
                {day === "unknown" ? "Unknown date" : formatDay(day)}
              </h3>
              <ol className="border-l-2 border-slate-200 pl-4 space-y-2">
                {list.map((e) => <TimelineRow key={e.id} event={e} />)}
              </ol>
            </section>
          ))}
        </section>
      </div>
    </div>
  );
}

function CaseEventsSection({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const { data: entries = [] } = useQuery({
    queryKey: ["case-timeline-entries", caseId],
    queryFn: () => listTimelineEntries(caseId),
  });
  const [adding, setAdding] = useState(false);
  const [occurred, setOccurred] = useState("");
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");

  const invalidate = () => qc.invalidateQueries({ queryKey: ["case-timeline-entries", caseId] });
  const addMut = useMutation({
    mutationFn: () => createTimelineEntry(caseId, {
      occurred_at: occurred.trim(), label: label.trim(), notes: notes.trim(),
    }),
    onSuccess: () => { setOccurred(""); setLabel(""); setNotes(""); setAdding(false); invalidate(); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteTimelineEntry(caseId, id),
    onSuccess: invalidate,
  });

  return (
    <section>
      <div className="flex items-baseline justify-between mb-2">
        <div>
          <h2 className="text-[15px] font-semibold text-slate-900">Case events</h2>
          <p className="text-xs text-slate-500">
            The detective's chronology of what happened — distinct from the
            system activity log below. {entries.length} entr{entries.length === 1 ? "y" : "ies"}.
          </p>
        </div>
        {!adding ? (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="px-2.5 py-1 text-xs rounded border border-slate-300 hover:bg-slate-50"
          >
            + Add event
          </button>
        ) : null}
      </div>

      <TimelineSuggestions caseId={caseId} existingLabels={new Set(entries.map((e) => e.label.toLowerCase()))} onAccepted={invalidate} />

      {adding ? (
        <div className="border border-slate-200 rounded p-3 mb-3 bg-slate-50/60 space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <label className="block">
              <span className="text-[11px] text-slate-600">When (free form)</span>
              <input
                className="mt-0.5 w-full border border-slate-300 rounded px-2 py-1 text-sm"
                value={occurred} onChange={(e) => setOccurred(e.target.value)}
                placeholder="e.g. 1945-08-15 17:00 or circa Aug 1945"
                autoFocus
              />
            </label>
            <label className="block col-span-2">
              <span className="text-[11px] text-slate-600">Label</span>
              <input
                className="mt-0.5 w-full border border-slate-300 rounded px-2 py-1 text-sm"
                value={label} onChange={(e) => setLabel(e.target.value)}
                placeholder="One short phrase describing what happened"
              />
            </label>
          </div>
          <label className="block">
            <span className="text-[11px] text-slate-600">Notes (optional)</span>
            <textarea
              className="mt-0.5 w-full border border-slate-300 rounded px-2 py-1 text-sm"
              rows={2}
              value={notes} onChange={(e) => setNotes(e.target.value)}
            />
          </label>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => { setAdding(false); setOccurred(""); setLabel(""); setNotes(""); }}
              className="px-3 py-1 text-sm rounded border border-slate-300 hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={addMut.isPending || !occurred.trim() || !label.trim()}
              onClick={() => addMut.mutate()}
              className="px-3 py-1 text-sm rounded bg-blue-600 text-white disabled:opacity-50"
            >
              {addMut.isPending ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      ) : null}

      {entries.length === 0 ? (
        <div className="border border-dashed border-slate-300 rounded p-6 text-center text-xs text-slate-500">
          No events yet. Add the dated facts of the case so you have a chronological
          narrative — or click "Suggest events" to extract them from the documents.
        </div>
      ) : (
        <ol className="border-l-2 border-emerald-200 pl-4 space-y-2">
          {entries.map((e) => <CaseEventRow key={e.id} entry={e} onDelete={() => deleteMut.mutate(e.id)} />)}
        </ol>
      )}
    </section>
  );
}

function CaseEventRow({ entry, onDelete }: { entry: TimelineEntryT; onDelete: () => void }) {
  const isAi = entry.source === "ai_suggested";
  return (
    <li className="relative group">
      <span className={`absolute -left-[22px] top-1.5 w-3 h-3 rounded-full ring-2 ring-white ${isAi ? "bg-purple-500" : "bg-emerald-500"}`} />
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="text-xs font-mono text-slate-600 shrink-0">{entry.occurred_at}</span>
            <span className="text-sm text-slate-900">{entry.label}</span>
            {isAi ? (
              <span className="text-[10px] uppercase tracking-wide text-purple-700">AI</span>
            ) : null}
          </div>
          {entry.notes ? (
            <div className="text-xs text-slate-600 mt-0.5 leading-relaxed">{entry.notes}</div>
          ) : null}
          {isAi && entry.rationale ? (
            <div className="text-[11px] text-purple-700 italic mt-0.5">{entry.rationale}</div>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onDelete}
          className="opacity-0 group-hover:opacity-100 text-[11px] text-slate-400 hover:text-red-700 shrink-0"
          title="Remove this event"
        >
          remove
        </button>
      </div>
    </li>
  );
}

function TimelineSuggestions({
  caseId, existingLabels, onAccepted,
}: { caseId: string; existingLabels: Set<string>; onAccepted: () => void }) {
  const [run, setRun] = useState(false);
  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["timeline-suggestions", caseId],
    queryFn: () => suggestTimelineEntries(caseId),
    enabled: run,
    staleTime: 5 * 60_000,
  });
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const acceptMut = useMutation({
    mutationFn: (s: TimelineEntrySuggestion) => createTimelineEntry(caseId, {
      occurred_at: s.occurred_at, label: s.label, notes: s.notes,
      source_document_id: s.source_document_id, rationale: s.rationale,
      source: "ai_suggested",
    }),
    onSuccess: onAccepted,
  });

  const visible = (data?.suggestions ?? []).filter(
    (s) => !dismissed.has(s.label) && !existingLabels.has(s.label.toLowerCase()),
  );

  return (
    <div className="border border-slate-200 rounded p-3 bg-slate-50/40 mb-3">
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <div>
          <div className="text-[12px] font-semibold text-slate-900">Suggest events with AI</div>
          <div className="text-[11px] text-slate-500">
            Pull dated events from the case documents. You accept each individually.
          </div>
        </div>
        <button
          type="button"
          onClick={() => { setRun(true); setDismissed(new Set()); refetch(); }}
          disabled={isFetching}
          className="px-2.5 py-1 text-xs rounded border border-blue-300 bg-white text-blue-800 hover:bg-blue-50 disabled:opacity-50 shrink-0"
        >
          {isFetching ? "Reading docs…" : run ? "Refresh" : "Suggest"}
        </button>
      </div>

      {error ? <div className="text-xs text-red-700">{(error as Error).message}</div> : null}
      {data?.reason ? <div className="text-xs text-slate-500 italic">{data.reason}</div> : null}

      {run && !isFetching && visible.length === 0 && !error && !data?.reason ? (
        <div className="text-xs text-slate-500 italic">
          {data?.suggestions.length ? "All suggestions handled." : "No new events found."}
        </div>
      ) : null}

      {visible.length > 0 ? (
        <ul className="space-y-1.5 mt-1">
          {visible.map((s: TimelineEntrySuggestion) => {
            const accepted = acceptMut.isSuccess && acceptMut.variables?.label === s.label;
            return (
              <li key={s.label} className="flex items-start gap-2 p-2 bg-white border border-slate-200 rounded">
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className="text-xs font-mono text-slate-600">{s.occurred_at}</span>
                    <span className="text-sm text-slate-900 font-medium">{s.label}</span>
                  </div>
                  {s.notes ? <div className="text-xs text-slate-600 mt-0.5">{s.notes}</div> : null}
                  {s.rationale ? (
                    <div className="text-[11px] text-purple-700 italic mt-0.5">{s.rationale}</div>
                  ) : null}
                  {s.source_document ? (
                    <div className="text-[10px] text-slate-400 mt-0.5 font-mono">{s.source_document}</div>
                  ) : null}
                </div>
                <div className="flex flex-col gap-1 shrink-0">
                  <button
                    type="button"
                    disabled={accepted || acceptMut.isPending}
                    onClick={() => acceptMut.mutate(s)}
                    className="px-2 py-0.5 text-[11px] rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {accepted ? "Added ✓" : "Accept"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setDismissed((p) => new Set(p).add(s.label))}
                    className="px-2 py-0.5 text-[11px] rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
                  >
                    Dismiss
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

function formatDay(day: string): string {
  const d = new Date(`${day}T00:00:00`);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diffDays = Math.round((today.getTime() - d.getTime()) / 86_400_000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "short", year: "numeric", month: "short", day: "numeric" });
}

// Color + label maps for audit-event types. Keeps the timeline visually
// scannable — a detective should know the rhythm of dot colors at a glance.
const TIMELINE_COLORS: Record<string, string> = {
  "case":         "bg-slate-400",
  "document":     "bg-blue-500",
  "media":        "bg-indigo-500",
  "conversation": "bg-blue-400",
  "message":      "bg-blue-400",
  "report":       "bg-emerald-500",
  "approval":     "bg-emerald-600",
  "retention":    "bg-amber-500",
  "vendor":       "bg-red-500",
  "purge":        "bg-red-500",
  "first_draft":  "bg-red-500",
};

function timelineColorFor(eventType: string): string {
  const prefix = eventType.split(".")[0] ?? "";
  return TIMELINE_COLORS[prefix] ?? "bg-slate-400";
}

function TimelineRow({ event }: { event: AuditEvent }) {
  const time = event.timestamp ? new Date(event.timestamp) : null;
  const dotCls = timelineColorFor(event.event_type);
  return (
    <li className="relative pb-1.5">
      <span
        className={`absolute -left-[22px] top-1.5 w-3 h-3 rounded-full ring-2 ring-white ${dotCls}`}
        title={event.event_type}
      />
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-sm text-slate-800">{event.summary || event.event_type}</div>
          <div className="text-[11px] text-slate-500 mt-0.5 flex flex-wrap gap-x-2">
            <span className="font-mono">{event.event_type}</span>
            {event.user_display ? <span>· {event.user_display}</span> : null}
          </div>
        </div>
        <span className="text-[11px] text-slate-500 shrink-0">
          {time ? time.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : ""}
        </span>
      </div>
    </li>
  );
}

function ChainTab({ caseId, reports }: { caseId: string; reports: Report[] }) {
  // §13663(c) view: every signed report has its own chain of custody.
  // Per-report PDF + a case-wide audit manifest PDF for the records officer.
  const signed = reports.filter((r) => r.status === "signed" || r.status === "exported");

  return (
    <div className="p-6 overflow-y-auto h-full">
      <div className="max-w-3xl">
        <header className="mb-4">
          <h2 className="text-[15px] font-semibold text-slate-900">Chain of custody</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Penal Code §13663(c). Append-only audit events linking every prompt,
            response, edit, and signature back to its officer + timestamp. Each
            signed report has a paired chain-of-custody PDF that surfaces this
            data in courtroom form.
          </p>
        </header>

        <ChainIntegrityCard />


        {signed.length === 0 ? (
          <div className="border border-dashed border-slate-300 rounded p-8 text-center text-sm text-slate-500">
            No signed reports yet — chain-of-custody artifacts are generated
            per signed report. The case-level audit manifest below is always
            available.
          </div>
        ) : (
          <ol className="space-y-3 mb-6">
            {signed.map((r) => <ChainReportCard key={r.id} caseId={caseId} report={r} />)}
          </ol>
        )}

        {/* Case-wide rollup — what the records officer sends to the city
            attorney when no specific report is requested. */}
        <section className="border-t border-slate-200 pt-4">
          <h3 className="text-[12px] font-semibold text-slate-700 mb-1">Case-wide rollup</h3>
          <p className="text-xs text-slate-500 mb-2">
            One PDF with every audit event on this case, hash-paired so tampering
            is visible. Use for subpoena / PRA response or city-attorney handoff.
          </p>
          <a
            href={`/launchpad/coldcase/api/cases/${caseId}/audit-manifest.pdf`}
            target="_blank"
            rel="noreferrer"
            className="inline-block px-3 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700"
          >
            Download case audit manifest (PDF) ↗
          </a>
        </section>
      </div>
    </div>
  );
}

function ChainIntegrityCard() {
  // Per-tenant — all events are chained as one stream, not per-case.
  // Shown on every case's Chain tab because that's where the city
  // attorney looks first when investigating any single artifact's lineage.
  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["audit-chain-report"],
    queryFn: getAuditChainReport,
    staleTime: 30_000,
  });

  if (error) {
    return (
      <div className="border border-amber-200 bg-amber-50/60 rounded p-3 mb-4 text-sm text-amber-900">
        Audit-chain verification unavailable: {(error as Error).message}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="border border-slate-200 rounded p-3 mb-4 text-xs text-slate-500">
        Verifying audit chain…
      </div>
    );
  }

  const toneCls = data.ok
    ? "border-emerald-200 bg-emerald-50/40"
    : "border-red-200 bg-red-50/40";
  const iconCls = data.ok
    ? "bg-emerald-600 text-white"
    : "bg-red-600 text-white";

  return (
    <section className={`border rounded p-3 mb-4 ${toneCls}`}>
      <div className="flex items-baseline gap-2">
        <span
          className={`shrink-0 w-5 h-5 flex items-center justify-center rounded-full text-xs font-bold ${iconCls}`}
          aria-label={data.ok ? "Chain intact" : "Chain broken"}
        >
          {data.ok ? "✓" : "!"}
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-semibold text-slate-900">
            {data.ok
              ? "Audit chain intact"
              : `Audit chain broken (${data.breaks.length} break${data.breaks.length === 1 ? "" : "s"})`}
          </div>
          <div className="text-[11px] text-slate-600 mt-0.5">
            <span>{data.event_count} events chained</span>
            {data.pre_chain_event_count > 0 ? (
              <span className="ml-2 text-amber-700">
                · {data.pre_chain_event_count} pre-chain (run rechain to integrate)
              </span>
            ) : null}
            <span className="ml-2 font-mono text-slate-500">
              tip {data.tip_hash.slice(0, 16)}…
            </span>
          </div>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="shrink-0 px-2 py-0.5 text-[11px] rounded border border-slate-300 bg-white hover:bg-slate-50 disabled:opacity-50"
        >
          {isFetching ? "Verifying…" : "Re-verify"}
        </button>
      </div>

      {!data.ok && data.breaks.length > 0 ? (
        <ul className="mt-2 pt-2 border-t border-red-200 space-y-1 text-[11px] text-red-900">
          {data.breaks.slice(0, 5).map((b) => (
            <li key={`${b.kind}-${b.event_id}`} className="flex items-baseline gap-2">
              <span className="font-mono text-red-700">seq&nbsp;{b.sequence}</span>
              <span>{b.detail}</span>
            </li>
          ))}
          {data.breaks.length > 5 ? (
            <li className="italic text-red-700">
              + {data.breaks.length - 5} more — see full report at <code>/admin/compliance/audit-chain</code>.
            </li>
          ) : null}
        </ul>
      ) : null}
    </section>
  );
}

function ChainReportCard({ caseId, report }: { caseId: string; report: Report }) {
  // Fetch the per-report chain to surface the linked event count + AI program(s).
  const { data } = useQuery({
    queryKey: ["report-chain", report.id],
    queryFn: () => getReportChain(report.id),
    staleTime: 60_000,
  });
  const events = data?.audit_events ?? [];
  const sig = report.signature;
  return (
    <li className="border border-slate-200 rounded p-3 bg-white">
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0">
          <div className="font-medium text-slate-900 truncate">{report.title}</div>
          <div className="text-xs text-slate-500 mt-0.5">
            {sig?.signed_at ? <>Signed {new Date(sig.signed_at).toLocaleString()}</> : null}
            {sig?.display_name ? <> · {sig.display_name}</> : null}
            {sig?.badge_number ? <> · badge {sig.badge_number}</> : null}
          </div>
        </div>
        <a
          href={`/launchpad/coldcase/api/reports/${report.id}/chain.pdf`}
          target="_blank"
          rel="noreferrer"
          className="shrink-0 px-2.5 py-1 text-xs rounded border border-slate-300 hover:bg-slate-50"
        >
          chain PDF ↗
        </a>
      </div>

      {/* AI programs identified — §13663(a)(1). */}
      {report.ai_programs_used.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {report.ai_programs_used.map((p, i) => (
            <span key={i} className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">
              {p.name} {p.version}
            </span>
          ))}
        </div>
      ) : null}

      {/* Mini chain — first 5 events building toward the signature. */}
      {events.length > 0 ? (
        <ol className="mt-3 border-l-2 border-slate-200 pl-3 space-y-1.5">
          {events.slice(0, 5).map((e) => (
            <li key={e.id} className="relative">
              <span
                className={`absolute -left-[14px] top-1.5 w-2 h-2 rounded-full ring-2 ring-white ${timelineColorFor(e.event_type)}`}
              />
              <div className="text-xs text-slate-700 truncate">{e.summary || e.event_type}</div>
              <div className="text-[10px] text-slate-500 font-mono">{e.event_type}</div>
            </li>
          ))}
          {events.length > 5 ? (
            <li className="text-[10px] text-slate-500 italic">
              + {events.length - 5} more events — see the chain PDF for the full record.
            </li>
          ) : null}
        </ol>
      ) : null}

      {/* Content hash for tamper-evidence. */}
      {sig?.content_sha256 ? (
        <div className="mt-2 text-[10px] font-mono text-slate-400 break-all">
          sha256: {sig.content_sha256}
        </div>
      ) : null}
    </li>
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
