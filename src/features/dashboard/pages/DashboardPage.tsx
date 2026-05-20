import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  listAuditEvents, listCases,
  type AuditEvent, type Case,
} from "@/lib/api/coldcase";
import { ROUTES, setHashPath } from "@/shell/routes";

/** Same fixture filter the cases list uses. Keeps SMOKE/F-prefixed test
 *  rows out of the detective's "My cases" view by default. */
const TEST_FIXTURE_PREFIX = /^(SMOKE|F\d|CC-SMOKE)/i;

/**
 * Detective-centric landing page (Phase A · PR 4).
 *
 * Three cards:
 *   - "Needs your action"   — unsigned reports, stale cases
 *   - "Recent activity"     — last N audit events across my cases
 *   - "My cases"            — last 8 by last_activity_at (from ?mine=true)
 *
 * Role-aware extensions (sergeant queue, city-attorney anomaly feed) land in
 * Phase B once tags + roles surface on the user.
 */
export default function DashboardPage() {
  const { data: myCasesRaw = [], isLoading: casesLoading } = useQuery({
    queryKey: ["dashboard", "my-cases"],
    // Pull more than the display cap so the fixture filter doesn't leave us
    // short. 24 is enough headroom for any realistic test/real ratio.
    queryFn: () => listCases({ mine: true, limit: 24 }),
    staleTime: 30_000,
  });
  const myCases = useMemo(
    () => myCasesRaw.filter((c) => !TEST_FIXTURE_PREFIX.test(c.case_number)).slice(0, 8),
    [myCasesRaw],
  );

  const { data: recentEvents } = useQuery({
    queryKey: ["dashboard", "recent-events"],
    queryFn: () => listAuditEvents({ limit: 10 }),
    staleTime: 30_000,
  });

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-semibold leading-tight">Cold Case</h1>
        <p className="text-sm text-slate-600 mt-1">
          Your cases and what needs your attention. SB-524 / Penal Code §13663 governance is
          handled in the background.
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <NeedsYourAction cases={myCases} />
        <RecentActivity events={recentEvents?.events ?? []} />
      </div>

      <MyCases cases={myCases} loading={casesLoading} />
    </div>
  );
}

// ── Cards ───────────────────────────────────────────────────────────────────

function NeedsYourAction({ cases }: { cases: Case[] }) {
  // Heuristics for Phase A — without a per-user "drafts" query, we infer from
  // case activity. Phase B will replace this with real counts pulled from the
  // backend (an `/admin/dashboard/me` endpoint that aggregates).
  const stale = cases.filter((c) => {
    if (!c.last_activity_at) return false;
    const days = (Date.now() - new Date(c.last_activity_at).getTime()) / 86_400_000;
    return days > 14;
  });
  const homicide = cases.filter((c) => c.classification === "homicide");

  return (
    <Card title="Needs your action" tone="warning">
      <ul className="space-y-2 text-sm">
        <ChecklistRow
          ok={stale.length === 0}
          label={
            stale.length === 0
              ? "No stale cases (all touched within 14 days)"
              : `${stale.length} case${stale.length === 1 ? "" : "s"} with no activity in 14+ days`
          }
          detail={
            stale.length > 0
              ? stale.slice(0, 3).map((c) => c.case_number).join(", ") +
                (stale.length > 3 ? "…" : "")
              : undefined
          }
        />
        <ChecklistRow
          ok={true}
          label={`${homicide.length} homicide case${homicide.length === 1 ? "" : "s"} on your queue`}
          detail="Homicide retention is indefinite per §13663(b)."
          neutral
        />
        <li className="text-xs text-slate-500 italic pt-2 border-t border-slate-100">
          Per-report "needs your signature" counts land in Phase B with a dashboard
          aggregator endpoint.
        </li>
      </ul>
    </Card>
  );
}

function RecentActivity({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) {
    return (
      <Card title="Recent activity">
        <p className="text-sm text-slate-500">No recent activity yet.</p>
      </Card>
    );
  }
  return (
    <Card title="Recent activity">
      <ul className="space-y-1.5 text-sm">
        {events.slice(0, 8).map((e) => (
          <li key={e.id} className="flex items-baseline gap-2">
            <span
              className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 shrink-0"
              title={e.event_type}
            >
              {e.event_type.split(".")[0]}
            </span>
            <span className="text-slate-700 truncate">{e.summary || e.event_type}</span>
            <span className="ml-auto shrink-0 text-[11px] text-slate-500">
              {e.timestamp ? relTime(new Date(e.timestamp)) : ""}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function MyCases({ cases, loading }: { cases: Case[]; loading: boolean }) {
  return (
    <Card title={`My cases (${cases.length})`}>
      {loading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : cases.length === 0 ? (
        <p className="text-sm text-slate-500">
          You haven't been assigned a case yet. Open the{" "}
          <button
            type="button"
            onClick={() => setHashPath(ROUTES.cases)}
            className="text-blue-700 hover:underline"
          >
            Cases
          </button>{" "}
          page to create one.
        </p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {cases.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => setHashPath(`${ROUTES.casePrefix}${c.id}`)}
                className="w-full text-left py-2 px-1 hover:bg-slate-50 grid grid-cols-12 gap-2 items-baseline rounded"
              >
                <span className="col-span-3 font-mono text-xs text-slate-700">
                  {c.case_number}
                </span>
                <span className="col-span-6 truncate">{c.title}</span>
                <span className="col-span-2 text-[11px] capitalize">
                  {/* Only surface classifications that change the legal handling
                      (homicide / sexual assault → indefinite retention) or are
                      otherwise discriminating. Suppress "other" — it's the
                      default and just adds visual noise on every row. */}
                  {c.classification === "other" ? (
                    <span className="text-slate-300">·</span>
                  ) : c.classification === "homicide" || c.classification === "sexual_assault" ? (
                    <span className="text-red-700 font-medium">
                      {c.classification.replace("_", " ")}
                    </span>
                  ) : (
                    <span className="text-slate-500">
                      {c.classification.replace("_", " ")}
                    </span>
                  )}
                </span>
                <span className="col-span-1 text-right text-[11px] text-slate-500">
                  {c.last_activity_at ? relTime(new Date(c.last_activity_at)) : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 pt-3 border-t border-slate-100">
        <button
          type="button"
          onClick={() => setHashPath(ROUTES.cases)}
          className="text-sm text-blue-700 hover:underline"
        >
          See all cases →
        </button>
      </div>
    </Card>
  );
}

// ── Primitives ──────────────────────────────────────────────────────────────

function Card({
  title, tone, children,
}: {
  title: string;
  tone?: "warning";
  children: React.ReactNode;
}) {
  const accent =
    tone === "warning"
      ? "border-amber-200 bg-amber-50/30"
      : "border-slate-200 bg-white";
  return (
    <section className={`border rounded p-4 ${accent}`}>
      <h2 className="text-[15px] font-semibold text-slate-900 mb-3">
        {title}
      </h2>
      {children}
    </section>
  );
}

function ChecklistRow({
  ok, label, detail, neutral = false,
}: { ok: boolean; label: string; detail?: string; neutral?: boolean }) {
  const dotCls = neutral
    ? "bg-slate-400"
    : ok
      ? "bg-emerald-500"
      : "bg-amber-500";
  return (
    <li className="flex items-start gap-2">
      <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${dotCls}`} />
      <div className="flex-1 min-w-0">
        <div className="text-slate-800">{label}</div>
        {detail ? <div className="text-xs text-slate-500 mt-0.5">{detail}</div> : null}
      </div>
    </li>
  );
}

function relTime(d: Date): string {
  const sec = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  if (sec < 86400 * 30) return `${Math.floor(sec / 86400)}d ago`;
  return d.toISOString().slice(0, 10);
}
