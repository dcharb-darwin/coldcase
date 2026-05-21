// Hypothesis tab — voice/text brain dump → AI structured hypotheses →
// detective-approved investigation list with cross-check findings.
//
// Phase 1: typed input only. Voice capture + audio upload land in Phase 2
// behind the same backend endpoints (BrainDump model carries the source).

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  acceptHypothesisFinding, checkHypothesis, createBrainDump, createHypothesis,
  deleteHypothesis, listHypotheses, suggestHypotheses, updateHypothesis,
  type Hypothesis, type HypothesisFinding, type HypothesisFindingKind,
  type HypothesisStatus, type HypothesisSuggestion,
} from "@/lib/api/coldcase";


const STATUS_LABELS: Record<HypothesisStatus, string> = {
  investigating: "Investigating",
  confirmed: "Confirmed",
  disproved: "Disproved",
  superseded: "Superseded",
};

const STATUS_CHIP_CLS: Record<HypothesisStatus, string> = {
  investigating: "bg-blue-50 text-blue-800 border-blue-200",
  confirmed: "bg-emerald-50 text-emerald-800 border-emerald-200",
  disproved: "bg-red-50 text-red-800 border-red-200",
  superseded: "bg-slate-100 text-slate-700 border-slate-300",
};

const FINDING_CHIP_CLS: Record<HypothesisFindingKind, string> = {
  supporting: "bg-emerald-50 text-emerald-800 border-emerald-200",
  contradicting: "bg-red-50 text-red-800 border-red-200",
  gap: "bg-amber-50 text-amber-800 border-amber-200",
};


export default function HypothesisTab({ caseId }: { caseId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["case-hypotheses", caseId],
    queryFn: () => listHypotheses(caseId),
    staleTime: 30_000,
  });

  const hypotheses = data?.hypotheses ?? [];
  const grouped = useMemo(() => {
    const active = hypotheses.filter((h) => h.status === "investigating");
    const closed = hypotheses.filter((h) => h.status !== "investigating");
    return { active, closed };
  }, [hypotheses]);

  return (
    <div className="p-6 overflow-y-auto h-full">
      <div className="max-w-4xl space-y-6">
        <header>
          <h2 className="text-[15px] font-semibold text-slate-900">Hypotheses</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Brain-dump freely (typed now; voice + upload coming next). AI hones
            the dump into structured, falsifiable hypotheses. Detective approves
            which to formally investigate. Cross-check against case docs finds
            supporting, contradicting, and gap evidence.
          </p>
        </header>

        <BrainDumpComposer caseId={caseId} />

        <section>
          <h3 className="text-[13px] font-semibold text-slate-900 mb-2">
            Investigating ({grouped.active.length})
          </h3>
          {isLoading ? (
            <div className="text-xs text-slate-500">Loading…</div>
          ) : grouped.active.length === 0 ? (
            <div className="border border-dashed border-slate-300 rounded p-6 text-center text-xs text-slate-500">
              No active hypotheses. Capture a brain dump above and approve the AI's
              proposals to start investigating.
            </div>
          ) : (
            <ul className="space-y-3">
              {grouped.active.map((h) => <HypothesisCard key={h.id} caseId={caseId} hypothesis={h} />)}
            </ul>
          )}
        </section>

        {grouped.closed.length > 0 ? (
          <section>
            <h3 className="text-[13px] font-semibold text-slate-900 mb-2">
              Closed ({grouped.closed.length})
            </h3>
            <ul className="space-y-3 opacity-80">
              {grouped.closed.map((h) => <HypothesisCard key={h.id} caseId={caseId} hypothesis={h} />)}
            </ul>
          </section>
        ) : null}
      </div>
    </div>
  );
}


// ── Brain-dump composer + suggestion review ──────────────────────────────

function BrainDumpComposer({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const [transcript, setTranscript] = useState("");
  const [dumpId, setDumpId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<HypothesisSuggestion[]>([]);
  const [model, setModel] = useState("");
  const [accepted, setAccepted] = useState<string[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const dumpMut = useMutation({
    mutationFn: (text: string) => createBrainDump(caseId, { transcript: text }),
  });

  const suggestMut = useMutation({
    mutationFn: (id: string) => suggestHypotheses(caseId, id),
    onSuccess: (resp) => {
      setSuggestions(resp.suggestions);
      setModel(resp.model ?? "");
      setAccepted([]);
      setDismissed(new Set());
    },
  });

  const acceptMut = useMutation({
    mutationFn: (s: HypothesisSuggestion) => createHypothesis(caseId, {
      title: s.title,
      body: s.body,
      rationale: s.rationale,
      brain_dump_id: dumpId ?? undefined,
      model,
    }),
    onSuccess: (_h, s) => {
      qc.invalidateQueries({ queryKey: ["case-hypotheses", caseId] });
      setAccepted((p) => p.includes(s.title) ? p : [...p, s.title]);
    },
  });

  const onCaptureAndExtract = async () => {
    const text = transcript.trim();
    if (!text) return;
    const dump = await dumpMut.mutateAsync(text);
    setDumpId(dump.id);
    suggestMut.mutate(dump.id);
  };

  const visibleSuggestions = suggestions.filter(
    (s) => !accepted.includes(s.title) && !dismissed.has(s.title),
  );

  const isBusy = dumpMut.isPending || suggestMut.isPending;

  return (
    <section className="border border-indigo-200 bg-indigo-50/30 rounded p-4">
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="text-[13px] font-semibold text-slate-900">Brain dump → hypotheses</h3>
        <span className="text-[11px] text-slate-500">
          {dumpId ? "Captured. Approve suggestions below." : "Speak freely on the page; AI structures it."}
        </span>
      </div>

      <textarea
        value={transcript}
        onChange={(e) => setTranscript(e.target.value)}
        rows={5}
        placeholder={"Driving back from the witness interview. Two things bug me. First, the timeline doesn't add up..."}
        className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm bg-white"
      />

      <div className="flex items-center gap-2 mt-2">
        <button
          type="button"
          disabled={!transcript.trim() || isBusy}
          onClick={onCaptureAndExtract}
          className="px-3 py-1.5 text-xs rounded bg-indigo-700 text-white hover:bg-indigo-800 disabled:opacity-50"
        >
          {isBusy ? "Reading…" : dumpId ? "Refresh hypotheses" : "Capture + suggest hypotheses"}
        </button>
        {dumpId ? (
          <button
            type="button"
            onClick={() => { setTranscript(""); setDumpId(null); setSuggestions([]); setAccepted([]); setDismissed(new Set()); }}
            className="px-2 py-1 text-xs rounded border border-slate-300 hover:bg-slate-50"
          >
            New dump
          </button>
        ) : null}
        <span className="text-[10px] text-slate-400 ml-auto">
          Voice capture + upload land next. Endpoint is provider-agnostic.
        </span>
      </div>

      {accepted.length > 0 ? (
        <div className="text-[11px] text-emerald-800 bg-emerald-50 border border-emerald-200 rounded px-2 py-1 mt-2">
          ✓ {accepted.length} hypothesis{accepted.length === 1 ? "" : "es"} under investigation — see list below.
        </div>
      ) : null}

      {suggestMut.error ? (
        <div className="text-xs text-red-700 mt-2">{(suggestMut.error as Error).message}</div>
      ) : null}

      {visibleSuggestions.length > 0 ? (
        <ul className="space-y-2 mt-3">
          {visibleSuggestions.map((s) => {
            const isPending = acceptMut.isPending && acceptMut.variables?.title === s.title;
            return (
              <li key={s.title} className="bg-white border border-slate-200 rounded p-2.5">
                <div className="flex items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-slate-900">{s.title}</div>
                    {s.body ? <div className="text-xs text-slate-700 mt-0.5 leading-snug">{s.body}</div> : null}
                    {s.rationale ? <div className="text-[11px] text-indigo-700 italic mt-1">{s.rationale}</div> : null}
                  </div>
                  <div className="flex flex-col gap-1 shrink-0">
                    <button
                      type="button"
                      disabled={isPending}
                      onClick={() => acceptMut.mutate(s)}
                      className="px-2 py-0.5 text-[11px] rounded bg-indigo-700 text-white hover:bg-indigo-800 disabled:opacity-50"
                    >
                      {isPending ? "Saving…" : "Investigate"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setDismissed((p) => new Set(p).add(s.title))}
                      className="px-2 py-0.5 text-[11px] rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}


// ── A single hypothesis with status + findings + check button ────────────

function HypothesisCard({ caseId, hypothesis: h }: { caseId: string; hypothesis: Hypothesis }) {
  const qc = useQueryClient();
  const [checking, setChecking] = useState(false);
  const [pendingFindings, setPendingFindings] = useState<(Omit<HypothesisFinding, "accepted_by" | "accepted_at" | "suggested_by_model"> & { _key: string })[]>([]);
  const [checkModel, setCheckModel] = useState("");
  const [error, setError] = useState<string>("");

  const statusMut = useMutation({
    mutationFn: (status: HypothesisStatus) => updateHypothesis(caseId, h.id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case-hypotheses", caseId] }),
  });
  const deleteMut = useMutation({
    mutationFn: () => deleteHypothesis(caseId, h.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case-hypotheses", caseId] }),
  });
  const acceptFindingMut = useMutation({
    mutationFn: (f: typeof pendingFindings[number]) => acceptHypothesisFinding(caseId, h.id, {
      kind: f.kind, excerpt: f.excerpt, rationale: f.rationale,
      source_doc_id: f.source_doc_id, source_doc_filename: f.source_doc_filename,
      model: checkModel,
    }),
    onSuccess: (_data, f) => {
      qc.invalidateQueries({ queryKey: ["case-hypotheses", caseId] });
      setPendingFindings((prev) => prev.filter((p) => p._key !== f._key));
    },
  });

  const runCheck = async () => {
    setError("");
    setChecking(true);
    try {
      const resp = await checkHypothesis(caseId, h.id);
      setCheckModel(resp.model ?? "");
      setPendingFindings(resp.findings.map((f, i) => ({ ...f, _key: `${f.kind}-${i}-${f.excerpt.slice(0, 12)}` })));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setChecking(false);
    }
  };

  return (
    <li className="border border-slate-200 rounded p-3 bg-white">
      <header className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[10px] capitalize shrink-0 ${STATUS_CHIP_CLS[h.status]}`}>
              {STATUS_LABELS[h.status]}
            </span>
            <h4 className="text-sm font-semibold text-slate-900">{h.title}</h4>
            {h.proposed_by_model ? (
              <span className="text-[10px] uppercase tracking-wide text-purple-700">AI</span>
            ) : null}
          </div>
          {h.body ? <p className="text-xs text-slate-700 mt-1 leading-relaxed">{h.body}</p> : null}
          {h.rationale ? (
            <p className="text-[11px] text-slate-500 italic mt-1">Rationale: {h.rationale}</p>
          ) : null}
        </div>
        <div className="shrink-0">
          <select
            value={h.status}
            onChange={(e) => statusMut.mutate(e.target.value as HypothesisStatus)}
            className="text-[11px] border border-slate-300 rounded px-1.5 py-0.5 bg-white"
          >
            <option value="investigating">Investigating</option>
            <option value="confirmed">Confirmed</option>
            <option value="disproved">Disproved</option>
            <option value="superseded">Superseded</option>
          </select>
        </div>
      </header>

      {/* Accepted findings */}
      {h.findings.length > 0 ? (
        <div className="mt-2 pt-2 border-t border-slate-100 space-y-1.5">
          <div className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold">
            Findings on file ({h.findings.length})
          </div>
          {h.findings.map((f, i) => <FindingRow key={i} finding={f} />)}
        </div>
      ) : null}

      {/* Check button + pending findings */}
      <div className="mt-2 pt-2 border-t border-slate-100">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-[11px] text-slate-500">
            AI cross-check against the case documents — supporting, contradicting, gaps.
          </span>
          <div className="flex gap-1.5 shrink-0">
            <button
              type="button"
              onClick={runCheck}
              disabled={checking}
              className="px-2.5 py-0.5 text-[11px] rounded border border-blue-300 bg-white text-blue-800 hover:bg-blue-50 disabled:opacity-50"
            >
              {checking ? "Checking…" : "Check evidence"}
            </button>
            <button
              type="button"
              onClick={() => { if (confirm(`Delete hypothesis "${h.title}"?`)) deleteMut.mutate(); }}
              className="px-2 py-0.5 text-[11px] rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
            >
              Delete
            </button>
          </div>
        </div>

        {error ? <div className="text-[11px] text-red-700 mt-1">{error}</div> : null}

        {pendingFindings.length > 0 ? (
          <ul className="space-y-1.5 mt-2">
            {pendingFindings.map((f) => {
              const isPending = acceptFindingMut.isPending && acceptFindingMut.variables?._key === f._key;
              return (
                <li key={f._key} className="border border-slate-200 rounded p-2 bg-slate-50/60">
                  <div className="flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2 flex-wrap">
                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full border text-[10px] capitalize ${FINDING_CHIP_CLS[f.kind]}`}>
                          {f.kind}
                        </span>
                        {f.source_doc_filename ? (
                          <span className="text-[10px] text-slate-500 font-mono">{f.source_doc_filename}</span>
                        ) : null}
                      </div>
                      {f.excerpt ? (
                        <div className="text-[11px] text-slate-800 mt-1 pl-2 border-l-2 border-slate-200">
                          "{f.excerpt}"
                        </div>
                      ) : null}
                      {f.rationale ? (
                        <div className="text-[11px] text-slate-600 italic mt-0.5">{f.rationale}</div>
                      ) : null}
                    </div>
                    <div className="flex flex-col gap-1 shrink-0">
                      <button
                        type="button"
                        disabled={isPending}
                        onClick={() => acceptFindingMut.mutate(f)}
                        className="px-2 py-0.5 text-[11px] rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        {isPending ? "Saving…" : "Add to record"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setPendingFindings((p) => p.filter((x) => x._key !== f._key))}
                        className="px-2 py-0.5 text-[11px] rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
                      >
                        Skip
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
    </li>
  );
}


function FindingRow({ finding: f }: { finding: HypothesisFinding }) {
  return (
    <div className="flex items-start gap-2">
      <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full border text-[10px] capitalize shrink-0 ${FINDING_CHIP_CLS[f.kind as HypothesisFindingKind]}`}>
        {f.kind}
      </span>
      <div className="flex-1 min-w-0">
        {f.excerpt ? (
          <div className="text-[11px] text-slate-800 pl-2 border-l-2 border-slate-200">"{f.excerpt}"</div>
        ) : null}
        {f.rationale ? (
          <div className="text-[10px] text-slate-500 italic mt-0.5">{f.rationale}</div>
        ) : null}
        {f.source_doc_filename ? (
          <div className="text-[10px] text-slate-400 font-mono mt-0.5">{f.source_doc_filename}</div>
        ) : null}
      </div>
    </div>
  );
}
