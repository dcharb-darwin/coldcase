import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  editReport,
  exportReport,
  getReport,
  getReportDiff,
  promoteMessageToReport,
  reportChainPdfUrl,
  reportDiffPdfUrl,
  reportPdfUrl,
  signReport,
  type Message,
  type Report,
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
        className="bg-white w-full max-w-3xl h-full overflow-y-auto shadow-2xl"
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
          <ReportEditor
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
    <div className="p-6">
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

function ReportEditor({
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
  const [displayName, setDisplayName] = useState("");
  const [badge, setBadge] = useState("");

  useEffect(() => {
    if (report) {
      setFinalText(report.final_text);
      setTitle(report.title);
      setDisplayName(report.signature?.display_name ?? "");
      setBadge(report.signature?.badge_number ?? "");
    }
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
      await editReport(reportId, { title, final_text: finalText });
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

  // ALL hooks must run on every render, before any conditional return —
  // moving useMemo below the `if (!report)` early-return below would violate
  // the Rules of Hooks and React panics with "Rendered more hooks than
  // during the previous render."
  const citationCount = useMemo(() => extractCitations(finalText).length, [finalText]);

  if (!report) {
    return <div className="p-6 text-slate-500">Loading report…</div>;
  }

  const isDraft = report.status === "draft";
  const isSigned = report.status === "signed" || report.status === "exported";

  return (
    <div className="p-6">
      <header className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold">
            {report.status === "draft" ? "Draft report" : "Official report"}
          </h2>
          <div className="text-xs text-slate-500 mt-1 flex items-center gap-2">
            <StatusBadge status={report.status} /> · ID <code className="text-[10px]">{report.id.slice(-8)}</code>
          </div>
        </div>
        <button type="button" onClick={onClose} className="text-slate-400 text-2xl leading-none px-2">
          ×
        </button>
      </header>

      {/* §13663(a)(1) banner */}
      <div className="rounded border border-amber-200 bg-amber-50 p-3 text-xs mb-4">
        <div className="font-semibold text-amber-900">AI Disclosure (Cal. Penal Code §13663(a)(1))</div>
        <div className="mt-1 text-amber-900/90">{report.statutory_disclosure}</div>
        {report.ai_programs_used.length > 0 ? (
          <div className="mt-1 text-amber-900/80">
            AI program(s): {report.ai_programs_used.map((p) => `${p.name} ${p.version || ""}`.trim()).join("; ")}
          </div>
        ) : null}
      </div>

      {/* Title */}
      <label className="block mb-3">
        <span className="text-sm text-slate-600">Title</span>
        <input
          className="mt-1 w-full border border-slate-300 rounded px-2 py-1.5 text-sm disabled:bg-slate-100"
          value={title}
          disabled={!isDraft}
          onChange={(e) => setTitle(e.target.value)}
        />
      </label>

      {/* Final text — editor + live preview */}
      <div className="mb-3">
        <div className="flex items-baseline justify-between">
          <span className="text-sm text-slate-600">
            Report body {isDraft ? "(editable — sign locks this)" : "(locked)"}
          </span>
          {isDraft ? (
            <span className="text-[11px] text-slate-500">
              {finalText.length} chars · {citationCount} citations
            </span>
          ) : null}
        </div>
        {isDraft ? (
          <textarea
            className="mt-1 w-full border border-slate-300 rounded px-2 py-1.5 text-sm font-mono"
            rows={12}
            value={finalText}
            onChange={(e) => setFinalText(e.target.value)}
          />
        ) : null}

        {/* Live preview: clickable citations against the current draft text. */}
        <div className="mt-2">
          <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">
            {isDraft
              ? "Live preview — click any citation to verify the source before signing"
              : "Signed text"}
          </div>
          <div className="border border-slate-300 rounded px-3 py-2 text-sm bg-slate-50 max-h-72 overflow-y-auto">
            <CitationText text={finalText} onCitationClick={onCitationClick} />
          </div>
        </div>
      </div>

      {/* First AI draft (always shown, read-only) */}
      <details className="mb-3 rounded border border-slate-200 bg-slate-50 p-3 text-xs">
        <summary className="cursor-pointer font-semibold text-slate-700">
          §13663(b) first AI draft — not an officer statement
        </summary>
        <div className="mt-2 text-slate-700 max-h-72 overflow-y-auto">
          <CitationText
            text={report.first_ai_draft_text_snapshot}
            onCitationClick={onCitationClick}
          />
        </div>
      </details>

      {/* Revision history (business rule #13) */}
      <details className="mb-4 rounded border border-slate-200 bg-slate-50 p-3 text-xs">
        <summary className="cursor-pointer font-semibold text-slate-700">
          Revision history ({report.revisions.length})
        </summary>
        <ol className="mt-2 space-y-2">
          {report.revisions.map((r) => (
            <li
              key={r.seq}
              className={`border rounded p-2 ${
                r.is_signed_revision
                  ? "border-emerald-300 bg-emerald-50"
                  : "border-slate-200 bg-white"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold">
                  Rev {r.seq} · {r.editor_display || r.editor_id}
                  {r.is_signed_revision ? (
                    <span className="ml-2 px-1.5 py-0.5 rounded bg-emerald-200 text-emerald-900 text-[10px]">
                      ✓ SIGNED
                    </span>
                  ) : null}
                </span>
                <span className="text-slate-500 text-[10px]">
                  {r.timestamp ? new Date(r.timestamp).toLocaleString() : ""} · {r.byte_count} B
                </span>
              </div>
              <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                sha256: {r.content_sha256.slice(0, 24)}…
              </div>
              {r.note ? <div className="text-[11px] text-slate-600 italic mt-0.5">{r.note}</div> : null}
              <details className="mt-1">
                <summary className="cursor-pointer text-[11px] text-blue-700">show text</summary>
                <div className="mt-1 max-h-48 overflow-y-auto bg-slate-50 border border-slate-200 rounded px-2 py-1">
                  <CitationText text={r.text} onCitationClick={onCitationClick} />
                </div>
              </details>
            </li>
          ))}
        </ol>
      </details>

      {/* F9 — Officer's Editorial Work (diff between AI first draft and signed text) */}
      <EditorialWorkAccordion report={report} onCitationClick={onCitationClick} />

      {/* Signature block */}
      <div className="rounded border border-slate-200 p-3 mb-4 text-sm">
        <div className="font-semibold mb-2">§13663(a)(2) — Officer attestation</div>
        {isSigned && report.signature ? (
          <div className="space-y-1 text-xs">
            <div><strong>Signed by:</strong> {report.signature.display_name}</div>
            <div><strong>Badge:</strong> {report.signature.badge_number || "—"}</div>
            <div><strong>At:</strong> {report.signature.signed_at}</div>
            <div className="font-mono text-[10px] break-all">
              <strong>Content hash:</strong> {report.signature.content_sha256}
            </div>
            <div className="italic text-slate-600 mt-2">"{report.signature.attestation_text}"</div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="text-[11px] text-slate-600 italic">
              Your signature uses your authenticated identity ({displayName || "current session"}).
              The badge number you enter is recorded next to your user id for auditor review.
              §13663(a)(2) requires the signer be the named officer.
            </div>
            <label className="block">
              <span className="text-xs text-slate-600">Badge #</span>
              <input
                className="mt-1 w-full border border-slate-300 rounded px-2 py-1 text-sm"
                value={badge}
                onChange={(e) => setBadge(e.target.value)}
                placeholder="e.g. 7787"
              />
            </label>
          </div>
        )}
      </div>

      {/* Errors */}
      {[editMut, signMut, exportMut].map((m, i) =>
        m.error ? (
          <div key={i} className="text-sm text-red-700 mb-2">
            {(m.error as Error).message}
          </div>
        ) : null
      )}

      {/* Actions */}
      <div className="flex flex-wrap justify-end gap-2 mt-2">
        {isDraft ? (
          <>
            <button
              type="button"
              onClick={() => editMut.mutate()}
              disabled={editMut.isPending}
              className="px-3 py-1.5 text-sm rounded border border-slate-300"
            >
              {editMut.isPending ? "Saving…" : "Save draft"}
            </button>
            <button
              type="button"
              onClick={() => signMut.mutate()}
              disabled={signMut.isPending}
              className="px-3 py-1.5 text-sm rounded bg-emerald-600 text-white disabled:opacity-50"
              title="§13663(a)(2): signing attests review + factual accuracy. Required before export."
            >
              {signMut.isPending ? "Signing…" : "Sign report"}
            </button>
          </>
        ) : null}
        {report.status === "signed" ? (
          <button
            type="button"
            onClick={() => exportMut.mutate()}
            disabled={exportMut.isPending}
            className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white disabled:opacity-50"
          >
            {exportMut.isPending ? "Exporting…" : "Export PDF"}
          </button>
        ) : null}
        {report.status === "exported" ? (
          <>
            <a
              href={reportPdfUrl(report.id)}
              target="_blank"
              rel="noreferrer"
              className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700"
              title="Your official report — goes in the case file."
            >
              📄 Signed report ↗
            </a>
            <a
              href={reportChainPdfUrl(report.id)}
              target="_blank"
              rel="noreferrer"
              className="px-3 py-1.5 text-sm rounded bg-amber-600 text-white hover:bg-amber-700"
              title="§13663(c) chain-of-custody audit trail — for legal review, not the case file."
            >
              🔎 Audit trail ↗
            </a>
          </>
        ) : null}
        <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm rounded border border-slate-300">
          Close
        </button>
      </div>
    </div>
  );
}

function EditorialWorkAccordion({
  report,
  onCitationClick,
}: {
  report: Report;
  onCitationClick: (filename: string, line: number) => void;
}) {
  void onCitationClick;
  const { data, isLoading, error } = useQuery({
    queryKey: ["report-diff", report.id, report.signed_at],
    queryFn: () => getReportDiff(report.id),
    enabled: !!report.id,
  });

  return (
    <details className="mb-4 rounded border border-blue-200 bg-blue-50/40 p-3 text-xs">
      <summary className="cursor-pointer font-semibold text-blue-900">
        Officer's editorial work — what you changed from the AI's first draft
      </summary>
      <div className="mt-2 text-[11px] text-blue-900/90 italic">
        Removing unsupported claims, verifying facts, and improving clarity are your
        professional responsibilities. The AI is a tool. Your signature means you
        reviewed everything and stand behind every claim that remained.
      </div>
      {isLoading ? <div className="mt-2 text-slate-500">Computing diff…</div> : null}
      {error ? <div className="mt-2 text-red-700">{(error as Error).message}</div> : null}
      {data ? (
        <>
          <div className="mt-3 text-[11px] text-slate-700">
            Similarity: <strong>{(data.stats.similarity_ratio * 100).toFixed(1)}%</strong>
            {" · "}Compared against: <em>{data.compared_to_label}</em>
          </div>
          {data.stats.no_edits ? (
            <div className="mt-2 px-2 py-1.5 rounded border border-emerald-200 bg-emerald-50 text-emerald-900">
              Officer signed the AI's first draft verbatim — no edits.
            </div>
          ) : (
            <div className="mt-3 text-sm leading-relaxed whitespace-pre-wrap p-3 rounded border border-slate-200 bg-white max-h-96 overflow-y-auto">
              {data.segments.map((seg, i) => {
                if (seg.op === "equal") {
                  return <span key={i} className="text-slate-600">{seg.text} </span>;
                }
                if (seg.op === "officer_added") {
                  return <u key={i} className="text-blue-800">{seg.text} </u>;
                }
                return <s key={i} className="text-slate-400">{seg.text} </s>;
              })}
            </div>
          )}
          <a
            href={reportDiffPdfUrl(report.id)}
            target="_blank"
            rel="noreferrer"
            className="inline-block mt-3 px-2 py-1 text-xs rounded border border-blue-300 bg-white hover:bg-blue-100 text-blue-800"
          >
            Download editorial-work PDF ↗
          </a>
        </>
      ) : null}
    </details>
  );
}


function StatusBadge({ status }: { status: Report["status"] }) {
  const map: Record<Report["status"], string> = {
    draft: "bg-amber-100 text-amber-800",
    signed: "bg-emerald-100 text-emerald-800",
    exported: "bg-blue-100 text-blue-800",
    superseded: "bg-slate-200 text-slate-600",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${map[status]}`}>
      {status}
    </span>
  );
}
