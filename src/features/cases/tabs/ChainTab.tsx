import { useQuery } from "@tanstack/react-query";
import {
  getAuditChainReport,
  getReportChain,
  type Report,
} from "@/lib/api/coldcase";
import { timelineColorFor } from "./TimelineTab";

export default function ChainTab({ caseId, reports }: { caseId: string; reports: Report[] }) {
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

function ChainReportCard({ caseId: _caseId, report }: { caseId: string; report: Report }) {
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

      {report.ai_programs_used.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {report.ai_programs_used.map((p, i) => (
            <span key={i} className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">
              {p.name} {p.version}
            </span>
          ))}
        </div>
      ) : null}

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

      {sig?.content_sha256 ? (
        <div className="mt-2 text-[10px] font-mono text-slate-400 break-all">
          sha256: {sig.content_sha256}
        </div>
      ) : null}
    </li>
  );
}
