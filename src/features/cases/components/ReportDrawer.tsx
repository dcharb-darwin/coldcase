import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  discoveryPackageDownloadUrl,
  editReport,
  exportDiscoveryPackage,
  exportReport,
  getReport,
  getReportDiff,
  promoteMessageToReport,
  reportChainPdfUrl,
  reportDiffPdfUrl,
  reportPdfUrl,
  reviseReport,
  signReport,
  type Message,
  type Report,
  type ReportRevision,
  type ReviseProposal,
} from "@/lib/api/coldcase";
import { caseKeys, reportKeys } from "../queryKeys";
import CitationText, { extractCitations } from "./CitationText";

type DrawerState =
  | { kind: "closed" }
  | { kind: "promote"; sourceMessage: Message }
  | { kind: "report"; reportId: string };

interface ReportDrawerProps {
  caseId: string;
  state: DrawerState;
  onClose: () => void;
  onCitationClick: (filename: string, line: number) => void;
}

export default function ReportDrawer({ caseId, state, onClose, onCitationClick }: ReportDrawerProps) {
  if (state.kind === "closed") return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <div
        className="bg-slate-50 w-full max-w-[1280px] h-full overflow-hidden shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {state.kind === "promote" ? (
          <PromoteForm
            caseId={caseId}
            sourceMessage={state.sourceMessage}
            onClose={onClose}
            onCitationClick={onCitationClick}
          />
        ) : (
          <ReportWorkspace
            caseId={caseId}
            reportId={state.reportId}
            onClose={onClose}
            onCitationClick={onCitationClick}
          />
        )}
      </div>
    </div>
  );
}

// ── Promote (unchanged behaviorally) ────────────────────────────────────────

function PromoteForm({
  caseId,
  sourceMessage,
  onClose,
  onCitationClick,
}: {
  caseId: string;
  sourceMessage: Message;
  onClose: () => void;
  onCitationClick: (filename: string, line: number) => void;
}) {
  const qc = useQueryClient();
  const [title, setTitle] = useState(() => `Report from ${new Date().toLocaleDateString()}`);

  const promoteMutation = useMutation({
    mutationFn: () => promoteMessageToReport({ title, message_id: sourceMessage.id }),
    onSuccess: (report: Report) => {
      qc.invalidateQueries({ queryKey: caseKeys.reports(caseId) });
      qc.invalidateQueries({ queryKey: caseKeys.conversations(caseId) });
      window.dispatchEvent(new CustomEvent("open-report", { detail: { reportId: report.id } }));
      onClose();
    },
  });

  return (
    <div className="p-6 bg-white h-full overflow-y-auto">
      <header className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold">Promote AI output to an official report</h2>
          <p className="text-xs text-slate-500 mt-1">
            This message will become the <strong>§13663(b) first AI draft</strong> and be retained
            for as long as the report is retained. It cannot be edited or removed afterward.
          </p>
        </div>
        <button type="button" onClick={onClose} className="text-slate-400 text-2xl leading-none px-2">
          ×
        </button>
      </header>

      <label className="block mb-3">
        <span className="text-sm text-slate-600">Report title</span>
        <input
          className="mt-1 w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </label>

      <div className="mt-2 rounded border border-amber-200 bg-amber-50 p-3 text-xs">
        <div className="font-semibold text-amber-900 mb-1">§13663(b) first AI draft (preview)</div>
        <div className="text-amber-900/90 max-h-72 overflow-y-auto">
          <CitationText text={sourceMessage.content} onCitationClick={onCitationClick} />
        </div>
        <div className="mt-2 text-amber-800/80">
          Model: <code>{sourceMessage.model || "—"}</code> ({sourceMessage.provider || "—"})
        </div>
      </div>

      {promoteMutation.error ? (
        <div className="mt-3 text-sm text-red-700">{(promoteMutation.error as Error).message}</div>
      ) : null}

      <div className="mt-5 flex justify-end gap-2">
        <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm rounded border border-slate-300">
          Cancel
        </button>
        <button
          type="button"
          disabled={promoteMutation.isPending || !title.trim()}
          onClick={() => promoteMutation.mutate()}
          className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white disabled:opacity-50"
        >
          {promoteMutation.isPending ? "Promoting…" : "Promote to report draft"}
        </button>
      </div>
    </div>
  );
}

// ── Report workspace ────────────────────────────────────────────────────────

type Phase = "review" | "refine" | "deliver";

function phaseForStatus(status: Report["status"]): Phase {
  if (status === "draft") return "refine";
  if (status === "signed") return "deliver";
  if (status === "exported") return "deliver";
  return "review";
}

export function ReportWorkspace({
  caseId,
  reportId,
  onClose,
  onCitationClick,
}: {
  caseId: string;
  reportId: string;
  onClose: () => void;
  onCitationClick: (filename: string, line: number) => void;
}) {
  const qc = useQueryClient();
  const { data: report, refetch } = useQuery({
    queryKey: reportKeys.detail(reportId),
    queryFn: () => getReport(reportId),
  });

  const [finalText, setFinalText] = useState("");
  const [title, setTitle] = useState("");
  const [badge, setBadge] = useState("");
  const [proposal, setProposal] = useState<ReviseProposal | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (report) {
      setFinalText(report.final_text);
      setTitle(report.title);
      setBadge(report.signature?.badge_number ?? "");
      setProposal(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report?.id]);

  const editMut = useMutation({
    mutationFn: () => editReport(reportId, { title, final_text: finalText }),
    onSuccess: () => {
      refetch();
      qc.invalidateQueries({ queryKey: caseKeys.reports(caseId) });
    },
  });

  const signMut = useMutation({
    mutationFn: async () => {
      // Save edits first, then sign. F19: signer identity comes from the
      // authenticated session server-side; only badge is sent in the body.
      if (finalText !== report?.final_text || title !== report?.title) {
        await editReport(reportId, { title, final_text: finalText });
      }
      return signReport(reportId, { badge_number: badge });
    },
    onSuccess: () => {
      refetch();
      qc.invalidateQueries({ queryKey: caseKeys.reports(caseId) });
    },
  });

  const exportMut = useMutation({
    mutationFn: () => exportReport(reportId, "file"),
    onSuccess: () => {
      refetch();
      qc.invalidateQueries({ queryKey: caseKeys.reports(caseId) });
    },
  });

  const citationCount = useMemo(() => extractCitations(finalText).length, [finalText]);

  if (!report) {
    return <div className="p-6 text-slate-500">Loading report…</div>;
  }

  const isDraft = report.status === "draft";
  const isSigned = report.status === "signed" || report.status === "exported";
  const phase = phaseForStatus(report.status);
  const dirty = isDraft && (finalText !== report.final_text || title !== report.title);

  const acceptProposal = (text: string) => {
    if (proposal?.applies_to === "selection" && textareaRef.current) {
      const el = textareaRef.current;
      const start = el.selectionStart ?? 0;
      const end = el.selectionEnd ?? finalText.length;
      setFinalText(finalText.slice(0, start) + text + finalText.slice(end));
    } else {
      setFinalText(text);
    }
    setProposal(null);
  };

  return (
    <div className="flex flex-col h-full">
      <WorkspaceHeader report={report} phase={phase} dirty={dirty} onClose={onClose} />

      <div className="flex-1 overflow-hidden grid grid-cols-12 gap-0 bg-slate-100">
        {/* Left: AI first draft + revision timeline */}
        <aside className="col-span-3 border-r border-slate-200 bg-white overflow-y-auto">
          <FirstDraftPanel report={report} onCitationClick={onCitationClick} />
          <RevisionTimeline revisions={report.revisions || []} onCitationClick={onCitationClick} />
        </aside>

        {/* Center: editable body + AI revise */}
        <main className="col-span-6 overflow-y-auto bg-white">
          <RefinePanel
            report={report}
            title={title}
            setTitle={setTitle}
            finalText={finalText}
            setFinalText={setFinalText}
            textareaRef={textareaRef}
            isDraft={isDraft}
            citationCount={citationCount}
            onCitationClick={onCitationClick}
            proposal={proposal}
            setProposal={setProposal}
            onAcceptProposal={acceptProposal}
          />
        </main>

        {/* Right: §13663 disclosure + sign + deliver */}
        <aside className="col-span-3 border-l border-slate-200 bg-white overflow-y-auto">
          <DisclosurePanel report={report} />
          {isDraft ? (
            <SignaturePanel
              badge={badge}
              setBadge={setBadge}
              onSign={() => signMut.mutate()}
              onSaveDraft={() => editMut.mutate()}
              signPending={signMut.isPending}
              savePending={editMut.isPending}
              dirty={dirty}
              error={(signMut.error || editMut.error) as Error | null}
            />
          ) : (
            <SignedPanel report={report} />
          )}
          {isSigned ? (
            <DeliverPanel
              caseId={caseId}
              report={report}
              onExport={() => exportMut.mutate()}
              exportPending={exportMut.isPending}
              error={exportMut.error as Error | null}
            />
          ) : null}
        </aside>
      </div>
    </div>
  );
}

// ── Header w/ phase indicator ───────────────────────────────────────────────

function WorkspaceHeader({
  report, phase, dirty, onClose,
}: { report: Report; phase: Phase; dirty: boolean; onClose: () => void }) {
  return (
    <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold truncate">📋 {report.title}</h2>
          <StatusBadge status={report.status} />
          {dirty ? <span className="text-[11px] text-amber-700">• unsaved changes</span> : null}
        </div>
        <div className="text-[11px] text-slate-500 mt-0.5">
          Report ID <code>{report.id.slice(-8)}</code>
          {report.signed_at ? <> · signed {new Date(report.signed_at).toLocaleString()}</> : null}
        </div>
      </div>
      <PhaseStepper phase={phase} />
      <button type="button" onClick={onClose} className="text-slate-400 text-2xl leading-none px-2">×</button>
    </header>
  );
}

function PhaseStepper({ phase }: { phase: Phase }) {
  const steps: { id: Phase; label: string }[] = [
    { id: "review", label: "1. Review" },
    { id: "refine", label: "2. Refine" },
    { id: "deliver", label: "3. Deliver" },
  ];
  const order = { review: 0, refine: 1, deliver: 2 };
  return (
    <ol className="flex items-center gap-1 text-xs">
      {steps.map((s) => {
        const state = order[s.id] < order[phase] ? "done" : order[s.id] === order[phase] ? "current" : "todo";
        const cls =
          state === "current" ? "bg-blue-600 text-white" :
          state === "done" ? "bg-emerald-100 text-emerald-800" :
          "bg-slate-100 text-slate-500";
        return <li key={s.id} className={`px-2 py-1 rounded ${cls}`}>{s.label}</li>;
      })}
    </ol>
  );
}

// ── Left pane: first draft + timeline ───────────────────────────────────────

function FirstDraftPanel({
  report, onCitationClick,
}: { report: Report; onCitationClick: (f: string, l: number) => void }) {
  return (
    <section className="p-4 border-b border-slate-200">
      <div className="text-[12px] font-semibold text-amber-900 mb-1">
        §13663(b) First AI draft
      </div>
      <div className="text-[11px] text-slate-500 mb-2 italic">
        Not an officer statement. Preserved for the life of the report.
      </div>
      <div className="rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs max-h-64 overflow-y-auto">
        <CitationText
          text={report.first_ai_draft_text_snapshot}
          onCitationClick={onCitationClick}
        />
      </div>
    </section>
  );
}

function RevisionTimeline({
  revisions, onCitationClick,
}: { revisions: ReportRevision[]; onCitationClick: (f: string, l: number) => void }) {
  const [openSeq, setOpenSeq] = useState<number | null>(null);
  return (
    <section className="p-4">
      <div className="text-[12px] font-semibold text-slate-700 mb-2">
        Revisions ({revisions.length})
      </div>
      <ol className="space-y-1.5">
        {revisions.map((r) => {
          const isOpen = openSeq === r.seq;
          return (
            <li
              key={r.seq}
              className={`border rounded text-xs ${
                r.is_signed_revision ? "border-emerald-300 bg-emerald-50" : "border-slate-200 bg-white"
              }`}
            >
              <button
                type="button"
                onClick={() => setOpenSeq(isOpen ? null : r.seq)}
                className="w-full text-left px-2 py-1.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold truncate">
                    Rev {r.seq} · {r.editor_display || r.editor_id}
                  </span>
                  {r.is_signed_revision ? (
                    <span className="px-1 py-0.5 rounded bg-emerald-200 text-emerald-900 text-[9px]">✓ SIGNED</span>
                  ) : null}
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">
                  {r.timestamp ? new Date(r.timestamp).toLocaleString() : ""} · {r.byte_count} B
                </div>
                {r.note ? <div className="text-[10px] text-slate-600 italic">{r.note}</div> : null}
              </button>
              {isOpen ? (
                <div className="border-t border-slate-200 px-2 py-1.5 max-h-48 overflow-y-auto bg-slate-50">
                  <CitationText text={r.text} onCitationClick={onCitationClick} />
                </div>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

// ── Center pane: refine ─────────────────────────────────────────────────────

function RefinePanel({
  report, title, setTitle, finalText, setFinalText, textareaRef, isDraft,
  citationCount, onCitationClick, proposal, setProposal, onAcceptProposal,
}: {
  report: Report;
  title: string;
  setTitle: (s: string) => void;
  finalText: string;
  setFinalText: (s: string) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  isDraft: boolean;
  citationCount: number;
  onCitationClick: (f: string, l: number) => void;
  proposal: ReviseProposal | null;
  setProposal: (p: ReviseProposal | null) => void;
  onAcceptProposal: (text: string) => void;
}) {
  return (
    <div className="p-6 space-y-4">
      <label className="block">
        <span className="text-[12px] font-semibold text-slate-700">Title</span>
        <input
          className="mt-1 w-full border border-slate-300 rounded px-2 py-1.5 text-sm disabled:bg-slate-100"
          value={title}
          disabled={!isDraft}
          onChange={(e) => setTitle(e.target.value)}
        />
      </label>

      <div>
        <div className="flex items-baseline justify-between mb-1">
          <span className="text-[12px] font-semibold text-slate-700">
            Report body {isDraft ? "" : "(locked)"}
          </span>
          {isDraft ? (
            <span className="text-[11px] text-slate-500">
              {finalText.length} chars · {citationCount} citations
            </span>
          ) : null}
        </div>
        {isDraft ? (
          <textarea
            ref={textareaRef}
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm font-mono leading-relaxed"
            rows={18}
            value={finalText}
            onChange={(e) => setFinalText(e.target.value)}
            placeholder="Edit the draft here. Use the AI Revise toolbar below to ask for changes."
          />
        ) : null}
      </div>

      {isDraft ? (
        <ReviseToolbar
          reportId={report.id}
          textareaRef={textareaRef}
          finalText={finalText}
          proposal={proposal}
          setProposal={setProposal}
          onAccept={onAcceptProposal}
          onCitationClick={onCitationClick}
        />
      ) : null}

      <div>
        <div className="text-[12px] font-semibold text-slate-700 mb-1">
          {isDraft ? "Live preview" : "Signed text"}
        </div>
        <div className="border border-slate-300 rounded px-3 py-2 text-sm bg-slate-50 max-h-72 overflow-y-auto">
          <CitationText text={finalText} onCitationClick={onCitationClick} />
        </div>
      </div>

      {/* Officer's editorial work — visible (not collapsed) so the diff is obvious */}
      <EditorialWorkPanel report={report} />
    </div>
  );
}

const QUICK_INSTRUCTIONS: { label: string; instruction: string; needsSelection?: boolean }[] = [
  { label: "Tighten", instruction: "Tighten this paragraph. Remove hedging. Keep every fact and every citation token.", needsSelection: true },
  { label: "Plain language", instruction: "Rewrite in plain language a jury could follow. Keep every citation token.", needsSelection: true },
  { label: "Add timeline", instruction: "Add a chronological timeline section near the top, in `YYYY-MM-DD HH:MM — event (source)` format, drawn only from the existing draft and the case documents." },
  { label: "Flag gaps", instruction: "List gaps and ambiguities a defense attorney could exploit. Append them at the end of the draft under a `## Known gaps` heading. Do not invent facts." },
];

function ReviseToolbar({
  reportId, textareaRef, finalText, proposal, setProposal, onAccept, onCitationClick,
}: {
  reportId: string;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  finalText: string;
  proposal: ReviseProposal | null;
  setProposal: (p: ReviseProposal | null) => void;
  onAccept: (text: string) => void;
  onCitationClick: (f: string, l: number) => void;
}) {
  const [custom, setCustom] = useState("");

  const reviseMut = useMutation({
    mutationFn: (args: { instruction: string; selected_text?: string }) =>
      reviseReport(reportId, args),
    onSuccess: (data) => setProposal(data),
  });

  const sendQuick = (instruction: string, needsSelection: boolean | undefined) => {
    const el = textareaRef.current;
    const selection = el && el.selectionStart !== el.selectionEnd
      ? finalText.slice(el.selectionStart, el.selectionEnd)
      : "";
    if (needsSelection && !selection) {
      alert("Select the text you want to rewrite, then click again.");
      return;
    }
    reviseMut.mutate({
      instruction,
      selected_text: selection || undefined,
    });
  };

  const sendCustom = () => {
    if (!custom.trim()) return;
    const el = textareaRef.current;
    const selection = el && el.selectionStart !== el.selectionEnd
      ? finalText.slice(el.selectionStart, el.selectionEnd)
      : "";
    reviseMut.mutate({
      instruction: custom.trim(),
      selected_text: selection || undefined,
    });
    setCustom("");
  };

  return (
    <div className="rounded border border-blue-200 bg-blue-50/40 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[12px] font-semibold text-blue-900">
          🤖 Ask AI to revise
        </span>
        <span className="text-[11px] text-blue-900/70">
          Proposals are never auto-applied. You accept or discard.
        </span>
      </div>
      <div className="flex flex-wrap gap-1 mb-2">
        {QUICK_INSTRUCTIONS.map((q) => (
          <button
            key={q.label}
            type="button"
            onClick={() => sendQuick(q.instruction, q.needsSelection)}
            disabled={reviseMut.isPending}
            className="text-xs px-2 py-1 rounded border border-blue-300 bg-white hover:bg-blue-100 disabled:opacity-50"
            title={q.needsSelection ? "Select text first, then click." : q.instruction}
          >
            {q.label}{q.needsSelection ? " (selection)" : ""}
          </button>
        ))}
      </div>
      <div className="flex gap-1">
        <input
          type="text"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") sendCustom(); }}
          placeholder='e.g. "Add the witness statement from doc 3 to the narrative section"'
          className="flex-1 border border-slate-300 rounded px-2 py-1 text-xs"
          disabled={reviseMut.isPending}
        />
        <button
          type="button"
          onClick={sendCustom}
          disabled={reviseMut.isPending || !custom.trim()}
          className="text-xs px-3 py-1 rounded bg-blue-600 text-white disabled:opacity-50"
        >
          {reviseMut.isPending ? "Asking…" : "Ask"}
        </button>
      </div>
      {reviseMut.error ? (
        <div className="mt-2 text-xs text-red-700">{(reviseMut.error as Error).message}</div>
      ) : null}

      {proposal ? (
        <ProposalPanel
          proposal={proposal}
          onAccept={onAccept}
          onDiscard={() => setProposal(null)}
          onCitationClick={onCitationClick}
        />
      ) : null}
    </div>
  );
}

function ProposalPanel({
  proposal, onAccept, onDiscard, onCitationClick,
}: {
  proposal: ReviseProposal;
  onAccept: (text: string) => void;
  onDiscard: () => void;
  onCitationClick: (f: string, l: number) => void;
}) {
  return (
    <div className="mt-3 rounded border border-blue-300 bg-white">
      <div className="px-2 py-1 border-b border-blue-200 bg-blue-50 text-[11px] text-blue-900 flex items-center justify-between">
        <span>
          ✨ AI proposal · {proposal.applies_to === "selection" ? "replaces your selection" : "replaces the whole draft"}
        </span>
        <span className="font-mono text-[10px] text-blue-900/70">
          {proposal.provider}:{proposal.model} · {proposal.completion_tokens} tok
        </span>
      </div>
      <div className="px-3 py-2 text-sm max-h-64 overflow-y-auto leading-relaxed whitespace-pre-wrap">
        <CitationText text={proposal.proposed_text} onCitationClick={onCitationClick} />
      </div>
      <div className="px-2 py-1 border-t border-blue-200 flex justify-end gap-1">
        <button
          type="button"
          onClick={onDiscard}
          className="text-xs px-2 py-1 rounded border border-slate-300"
        >
          Discard
        </button>
        <button
          type="button"
          onClick={() => onAccept(proposal.proposed_text)}
          className="text-xs px-2 py-1 rounded bg-emerald-600 text-white"
        >
          Accept into draft
        </button>
      </div>
    </div>
  );
}

function EditorialWorkPanel({ report }: { report: Report }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["report-diff", report.id, report.signed_at],
    queryFn: () => getReportDiff(report.id),
    enabled: !!report.id,
  });
  return (
    <section className="rounded border border-slate-200 bg-white p-3">
      <div className="text-[12px] font-semibold text-slate-700 mb-1">
        Editorial work — what you changed from the AI's first draft
      </div>
      {isLoading ? <div className="text-xs text-slate-500">Computing diff…</div> : null}
      {error ? <div className="text-xs text-red-700">{(error as Error).message}</div> : null}
      {data ? (
        <>
          <div className="text-[11px] text-slate-700 mb-2">
            Similarity: <strong>{(data.stats.similarity_ratio * 100).toFixed(1)}%</strong>
            {" · "}compared against <em>{data.compared_to_label}</em>
          </div>
          {data.stats.no_edits ? (
            <div className="px-2 py-1.5 rounded border border-emerald-200 bg-emerald-50 text-emerald-900 text-xs">
              Officer accepted the AI's first draft verbatim — no edits.
            </div>
          ) : (
            <div className="text-sm leading-relaxed whitespace-pre-wrap p-2 rounded border border-slate-200 bg-slate-50 max-h-72 overflow-y-auto">
              {data.segments.map((seg, i) => {
                if (seg.op === "equal") return <span key={i} className="text-slate-600">{seg.text} </span>;
                if (seg.op === "officer_added") return <u key={i} className="text-blue-800">{seg.text} </u>;
                return <s key={i} className="text-slate-400">{seg.text} </s>;
              })}
            </div>
          )}
          <a
            href={reportDiffPdfUrl(report.id)}
            target="_blank"
            rel="noreferrer"
            className="inline-block mt-2 text-[11px] text-blue-700 hover:underline"
          >
            Download editorial-work PDF ↗
          </a>
        </>
      ) : null}
    </section>
  );
}

// ── Right pane: disclosure + sign + deliver ─────────────────────────────────

function DisclosurePanel({ report }: { report: Report }) {
  return (
    <section className="p-4 border-b border-slate-200">
      <div className="text-[12px] font-semibold text-amber-900 mb-1">
        AI disclosure (§13663(a)(1))
      </div>
      <div className="rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-[11px] text-amber-900">
        {report.statutory_disclosure}
      </div>
      {report.ai_programs_used.length > 0 ? (
        <div className="mt-2 text-[11px] text-slate-700">
          <div className="font-semibold mb-0.5">AI program(s)</div>
          <ul className="space-y-0.5">
            {report.ai_programs_used.map((p, i) => (
              <li key={i} className="font-mono">{p.name} {p.version}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function SignaturePanel({
  badge, setBadge, onSign, onSaveDraft, signPending, savePending, dirty, error,
}: {
  badge: string;
  setBadge: (s: string) => void;
  onSign: () => void;
  onSaveDraft: () => void;
  signPending: boolean;
  savePending: boolean;
  dirty: boolean;
  error: Error | null;
}) {
  return (
    <section className="p-4 border-b border-slate-200">
      <div className="text-[12px] font-semibold text-slate-700 mb-1">
        Sign (§13663(a)(2))
      </div>
      <div className="text-[11px] text-slate-600 mb-2">
        Your signature uses your authenticated session identity. The badge below
        is recorded in the audit log next to your user id for reviewer cross-check.
      </div>
      <label className="block mb-2">
        <span className="text-[11px] text-slate-600">Badge #</span>
        <input
          type="text"
          value={badge}
          onChange={(e) => setBadge(e.target.value)}
          placeholder="e.g. 7787"
          className="mt-0.5 w-full border border-slate-300 rounded px-2 py-1 text-sm"
        />
      </label>
      {error ? <div className="text-xs text-red-700 mb-2">{error.message}</div> : null}
      <div className="flex flex-col gap-1.5">
        <button
          type="button"
          onClick={onSaveDraft}
          disabled={savePending || !dirty}
          className="px-2 py-1.5 text-xs rounded border border-slate-300 disabled:opacity-50"
        >
          {savePending ? "Saving…" : dirty ? "Save draft" : "Saved"}
        </button>
        <button
          type="button"
          onClick={onSign}
          disabled={signPending}
          className="px-2 py-1.5 text-sm rounded bg-emerald-600 text-white disabled:opacity-50 font-medium"
          title="§13663(a)(2): signing attests review and factual accuracy. Required before export."
        >
          {signPending ? "Signing…" : "✓ Sign report"}
        </button>
      </div>
    </section>
  );
}

function SignedPanel({ report }: { report: Report }) {
  if (!report.signature) return null;
  return (
    <section className="p-4 border-b border-slate-200">
      <div className="text-[12px] font-semibold text-emerald-700 mb-1">
        ✓ Signed (§13663(a)(2))
      </div>
      <div className="text-xs space-y-0.5">
        <div><strong>By:</strong> {report.signature.display_name}</div>
        <div><strong>Badge:</strong> {report.signature.badge_number || "—"}</div>
        <div><strong>At:</strong> {report.signature.signed_at ? new Date(report.signature.signed_at).toLocaleString() : "—"}</div>
      </div>
      <div className="mt-2 font-mono text-[10px] text-slate-500 break-all">
        sha256: {report.signature.content_sha256.slice(0, 32)}…
      </div>
      <div className="mt-2 italic text-[11px] text-slate-600">
        "{report.signature.attestation_text}"
      </div>
    </section>
  );
}

function DeliverPanel({
  caseId, report, onExport, exportPending, error,
}: {
  caseId: string;
  report: Report;
  onExport: () => void;
  exportPending: boolean;
  error: Error | null;
}) {
  const [discoveryUrl, setDiscoveryUrl] = useState<string | null>(null);
  const discoveryMut = useMutation({
    mutationFn: () => exportDiscoveryPackage(caseId, {
      reason: `Discovery package for signed report ${report.id.slice(-8)}`,
      report_ids: [report.id],
    }),
    onSuccess: (pkg) => setDiscoveryUrl(discoveryPackageDownloadUrl(caseId, pkg.zip_filename)),
  });

  const exported = report.status === "exported";
  return (
    <section className="p-4">
      <div className="text-[12px] font-semibold text-blue-700 mb-2">
        Deliver
      </div>
      {!exported ? (
        <>
          <div className="text-[11px] text-slate-600 mb-2">
            Render the §13663-compliant PDF + chain-of-custody bundle.
          </div>
          <button
            type="button"
            onClick={onExport}
            disabled={exportPending}
            className="w-full px-2 py-1.5 text-sm rounded bg-blue-600 text-white disabled:opacity-50 font-medium"
          >
            {exportPending ? "Exporting…" : "📦 Export to PDF"}
          </button>
          {error ? <div className="text-xs text-red-700 mt-2">{error.message}</div> : null}
        </>
      ) : (
        <div className="space-y-2">
          <a
            href={reportPdfUrl(report.id)}
            target="_blank"
            rel="noreferrer"
            className="block w-full text-center px-2 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 font-medium"
            title="The signed report. Attach to case file."
          >
            📄 Signed report PDF ↗
          </a>
          <a
            href={reportChainPdfUrl(report.id)}
            target="_blank"
            rel="noreferrer"
            className="block w-full text-center px-2 py-1.5 text-sm rounded bg-amber-600 text-white hover:bg-amber-700"
            title="§13663(c) chain-of-custody audit trail."
          >
            🔎 Chain-of-custody PDF ↗
          </a>
          <button
            type="button"
            onClick={() => discoveryMut.mutate()}
            disabled={discoveryMut.isPending}
            className="w-full px-2 py-1.5 text-sm rounded border border-blue-300 bg-white hover:bg-blue-50 text-blue-800 disabled:opacity-50"
            title="Hash-pinned ZIP — report + chain + source documents. Shareable with the DA."
          >
            {discoveryMut.isPending ? "Building…" : "🗄️ Generate discovery package"}
          </button>
          {discoveryUrl ? (
            <a
              href={discoveryUrl}
              target="_blank"
              rel="noreferrer"
              className="block text-[11px] text-blue-700 hover:underline truncate"
              title={discoveryUrl}
            >
              ↓ download package
            </a>
          ) : null}
          {discoveryMut.error ? (
            <div className="text-xs text-red-700">{(discoveryMut.error as Error).message}</div>
          ) : null}

          <EvidenceComHandoff report={report} />
        </div>
      )}
    </section>
  );
}

function EvidenceComHandoff({ report }: { report: Report }) {
  const [copied, setCopied] = useState<"" | "ref" | "url">("");
  const sha = report.signature?.content_sha256 ?? "";
  // Filename the agency would use when filing the AI output in evidence.com.
  // Slugify the title down to ascii-safe characters so the filename stays
  // portable across uploaders that reject spaces or unicode.
  const titleSlug = report.title.toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "report";
  const filename = `coldcase-${titleSlug}-${report.id.slice(-8)}.pdf`;
  const pdfUrl = `${window.location.origin}${reportPdfUrl(report.id)}`;
  // Pre-baked reference block the detective can paste into evidence.com's
  // description field — covers what an auditor needs to tie the artifact
  // back to its §13663 chain without opening Cold Case.
  const reference = [
    `Title: ${report.title}`,
    `Report ID: ${report.id}`,
    `Case ID: ${report.case_id}`,
    `Status: ${report.status}`,
    `Signed by: ${report.signature?.display_name ?? "(unsigned)"}`,
    `Signed at: ${report.signature?.signed_at ?? ""}`,
    `Content sha256: ${sha}`,
    `AI program(s): ${report.ai_programs_used.map(p => `${p.name} ${p.version}`).join("; ")}`,
    `Source: Cold Case §13663 workflow`,
  ].join("\n");

  const copy = async (text: string, which: "ref" | "url") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(which);
      setTimeout(() => setCopied(""), 2000);
    } catch {
      // clipboard API can be blocked; fall back to a prompt
      window.prompt("Copy:", text);
    }
  };

  return (
    <div className="mt-3 pt-3 border-t border-slate-200">
      <div className="text-[12px] font-semibold text-slate-700 mb-1">
        Next: file in evidence.com
      </div>
      <div className="text-[11px] text-slate-600 mb-2 leading-snug">
        Cold Case is the §13663 chain of custody. Your case-of-record still
        lives in evidence.com — download the signed PDF and upload it there
        with the reference block below.
      </div>
      <div className="space-y-1.5">
        <a
          href={reportPdfUrl(report.id)}
          download={filename}
          className="block w-full text-center px-2 py-1.5 text-xs rounded bg-slate-700 text-white hover:bg-slate-800"
          title={`Download as ${filename}`}
        >
          ↓ Download "{filename}"
        </a>
        <button
          type="button"
          onClick={() => copy(reference, "ref")}
          className="w-full px-2 py-1 text-[11px] rounded border border-slate-300 bg-white hover:bg-slate-50 text-slate-700"
          title="Paste this into evidence.com's description field"
        >
          {copied === "ref" ? "✓ Copied reference" : "📋 Copy evidence.com reference"}
        </button>
        <button
          type="button"
          onClick={() => copy(pdfUrl, "url")}
          className="w-full px-2 py-1 text-[11px] rounded border border-slate-300 bg-white hover:bg-slate-50 text-slate-700"
          title="Permalink back to the signed PDF"
        >
          {copied === "url" ? "✓ Copied URL" : "🔗 Copy PDF permalink"}
        </button>
      </div>
      <details className="mt-2">
        <summary className="cursor-pointer text-[11px] text-slate-500">show reference</summary>
        <pre className="mt-1 text-[10px] bg-slate-50 border border-slate-200 rounded p-2 whitespace-pre-wrap font-mono">{reference}</pre>
      </details>
    </div>
  );
}

// ── Status badge ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: Report["status"] }) {
  const map: Record<Report["status"], string> = {
    draft: "bg-amber-100 text-amber-800",
    signed: "bg-emerald-100 text-emerald-800",
    exported: "bg-blue-100 text-blue-800",
    superseded: "bg-slate-200 text-slate-600",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${map[status]}`}>
      {status}
    </span>
  );
}
