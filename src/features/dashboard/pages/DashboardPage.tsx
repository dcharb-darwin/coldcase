import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getCrossCaseConflicts, getDashboardInsights,
  listAuditEvents, listCases, listTags,
  type AuditEvent, type Case, type CrossCaseConflictHit,
  type RecurringPerson, type SimilarCasePair,
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
  // Hide fixtures up-front; tag filtering + the 8-row display cap apply
  // inside MyCases so the chip row can show realistic counts and the cap
  // doesn't accidentally exclude matching tagged rows.
  const myCases = useMemo(
    () => myCasesRaw.filter((c) => !TEST_FIXTURE_PREFIX.test(c.case_number)),
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

      <CrossCaseInsights />
      <CrossCaseRoleConflicts />

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
  const [activeTagSlugs, setActiveTagSlugs] = useState<string[]>([]);

  // Tag chips for filtering — only show slugs actually present on the
  // current case set, user + system merged. Same convention as the
  // /cases list filter row.
  const inUseTags = useMemo(() => {
    const seen = new Map<string, { slug: string; label: string; kind: "user" | "system" }>();
    for (const c of cases) {
      for (const t of c.tags ?? []) {
        if (!seen.has(t.slug)) seen.set(t.slug, { slug: t.slug, label: t.label, kind: t.kind });
      }
    }
    return [...seen.values()].sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === "user" ? -1 : 1;
      return a.label.localeCompare(b.label);
    });
  }, [cases]);

  const { data: vocab = [] } = useQuery({
    queryKey: ["tags", "vocab"],
    queryFn: listTags,
    staleTime: 5 * 60_000,
    enabled: inUseTags.length > 0,
  });
  const vocabBySlug = useMemo(() => {
    const m = new Map<string, string>();
    vocab.forEach((t) => m.set(t.slug, t.description));
    return m;
  }, [vocab]);

  const toggleTag = (slug: string) => setActiveTagSlugs((prev) =>
    prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug],
  );

  const filtered = useMemo(() => {
    if (activeTagSlugs.length === 0) return cases;
    return cases.filter((c) => {
      const have = new Set((c.tags ?? []).map((t) => t.slug));
      return activeTagSlugs.every((s) => have.has(s));
    });
  }, [cases, activeTagSlugs]);
  // Cap display at 8 AFTER filtering so a narrow filter doesn't blank
  // the card just because the matches sit past the cap on the raw list.
  const visible = filtered.slice(0, 8);

  return (
    <Card title={`My cases (${filtered.length}${filtered.length !== cases.length ? ` of ${cases.length}` : ""})`}>
      {inUseTags.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5 mb-3 -mt-1">
          {inUseTags.map((t) => {
            const active = activeTagSlugs.includes(t.slug);
            const isSystem = t.kind === "system";
            return (
              <button
                key={t.slug}
                type="button"
                onClick={() => toggleTag(t.slug)}
                className={
                  "inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium transition-colors " +
                  (active
                    ? "bg-blue-600 text-white border-blue-600 hover:bg-blue-700"
                    : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50")
                }
                title={vocabBySlug.get(t.slug) ?? t.label}
              >
                <span className="opacity-70">{isSystem ? "🔒" : "#"}</span>
                {t.label}
              </button>
            );
          })}
          {activeTagSlugs.length > 0 ? (
            <button
              type="button"
              onClick={() => setActiveTagSlugs([])}
              className="text-[11px] text-slate-500 hover:text-slate-800 ml-1 underline"
            >
              clear
            </button>
          ) : null}
        </div>
      ) : null}

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
      ) : filtered.length === 0 ? (
        <p className="text-sm text-slate-500 italic">No cases match the current filter.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {visible.map((c) => (
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

function CrossCaseInsights() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard", "insights"],
    queryFn: getDashboardInsights,
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <Card title="Cross-case insights">
        <div className="text-xs text-slate-500">Computing…</div>
      </Card>
    );
  }
  if (error) {
    return (
      <Card title="Cross-case insights">
        <div className="text-xs text-red-700">{(error as Error).message}</div>
      </Card>
    );
  }
  const recurring = data?.recurring_persons ?? [];
  const pairs = data?.similar_case_pairs ?? [];
  if (recurring.length === 0 && pairs.length === 0) {
    return (
      <Card title="Cross-case insights">
        <p className="text-xs text-slate-500">
          Nothing recurring yet. People who appear on multiple of your cases —
          and tag-similar case pairs — will surface here as your caseload grows.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Cross-case insights">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
        <div>
          <h3 className="text-[12px] font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
            Recurring people
          </h3>
          {recurring.length === 0 ? (
            <p className="text-xs text-slate-500 italic">
              No person appears on more than one of your cases yet.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {recurring.map((r) => <RecurringPersonRow key={`${r.name}-${r.role}`} row={r} />)}
            </ul>
          )}
        </div>
        <div>
          <h3 className="text-[12px] font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
            Tag-similar case pairs
          </h3>
          {pairs.length === 0 ? (
            <p className="text-xs text-slate-500 italic">
              No tag overlap with your other cases yet.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {pairs.map((p) => <SimilarPairRow key={`${p.your_case_id}-${p.other_case_id}`} row={p} />)}
            </ul>
          )}
        </div>
      </div>
    </Card>
  );
}

function RecurringPersonRow({ row }: { row: RecurringPerson }) {
  const danger = row.role === "suspect" || row.role === "person_of_interest";
  const firstCaseId = row.your_case_ids[0];
  return (
    <li>
      <button
        type="button"
        onClick={() => firstCaseId && setHashPath(`${ROUTES.casePrefix}${firstCaseId}`)}
        className="w-full text-left border border-slate-200 rounded p-2 hover:border-blue-400 hover:bg-blue-50/40"
        title={`Open ${row.your_case_numbers[0] ?? "first case"}`}
      >
        <div className="flex items-baseline gap-2">
          <span className="font-medium text-slate-900 truncate flex-1">{row.name}</span>
          <span className={
            "text-[11px] capitalize " + (danger ? "text-red-700 font-medium" : "text-slate-500")
          }>
            {row.role.replace("_", " ")}
          </span>
          {row.ai_sourced_any ? (
            <span className="text-[10px] uppercase tracking-wide text-purple-700">AI</span>
          ) : null}
        </div>
        <div className="text-[11px] text-slate-500 mt-0.5 font-mono">
          {row.case_count} cases · {row.your_case_numbers.join(" · ")}
        </div>
      </button>
    </li>
  );
}

function SimilarPairRow({ row }: { row: SimilarCasePair }) {
  return (
    <li>
      <button
        type="button"
        onClick={() => setHashPath(`${ROUTES.casePrefix}${row.your_case_id}`)}
        className="w-full text-left border border-slate-200 rounded p-2 hover:border-blue-400 hover:bg-blue-50/40"
      >
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-xs text-slate-700">{row.your_case_number}</span>
          <span className="text-slate-400 text-xs">↔</span>
          <span className="font-mono text-xs text-slate-700">{row.other_case_number}</span>
          {!row.other_is_yours ? (
            <span className="text-[10px] uppercase tracking-wide text-slate-400">other</span>
          ) : null}
          <span className="ml-auto text-[11px] font-mono text-slate-500">
            {Math.round(row.score * 100)}%
          </span>
        </div>
        <div className="flex flex-wrap gap-1 mt-1">
          {row.shared_tag_labels.map((lbl) => (
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
}

function CrossCaseRoleConflicts() {
  // Surfaces query 5 of the graph layer — persons who appear on multiple
  // cases under DIFFERENT roles. This is a Brady/credibility risk: a
  // witness on case A who's a suspect on case B might be impeachable.
  // Backend already scopes to the caller's caseload via mine=true.
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard", "cross-case-conflicts"],
    queryFn: () => getCrossCaseConflicts({ mine: true }),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <Card title="Cross-case role conflicts" tone="warning">
        <div className="text-xs text-slate-500">Computing…</div>
      </Card>
    );
  }
  if (error) {
    return (
      <Card title="Cross-case role conflicts" tone="warning">
        <div className="text-xs text-red-700">{(error as Error).message}</div>
      </Card>
    );
  }
  const hits = data?.hits ?? [];

  return (
    <Card title={`Cross-case role conflicts${hits.length > 0 ? ` (${hits.length})` : ""}`} tone={hits.length > 0 ? "warning" : undefined}>
      <p className="text-xs text-slate-600 mb-2">
        People who appear on multiple of your cases under{" "}
        <strong>different roles</strong> — a witness on one case may be a
        suspect on another. Brady/credibility risk worth a second look before
        the case goes to the DA.
      </p>
      {hits.length === 0 ? (
        <p className="text-xs text-slate-500 italic">
          No role conflicts found on your caseload. People who appear on
          multiple cases under the <em>same</em> role show up in "Cross-case
          insights" above.
        </p>
      ) : (
        <ul className="space-y-2">
          {hits.map((h) => <RoleConflictRow key={h.person_id} hit={h} />)}
        </ul>
      )}
    </Card>
  );
}

function RoleConflictRow({ hit }: { hit: CrossCaseConflictHit }) {
  // Pre-bucket appearances by role for a compact visual.
  const byRole = new Map<string, CrossCaseConflictHit["appearances"]>();
  for (const a of hit.appearances) {
    const arr = byRole.get(a.role) ?? [];
    arr.push(a);
    byRole.set(a.role, arr);
  }
  return (
    <li className="border border-amber-200 rounded p-2.5 bg-white">
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="text-sm font-semibold text-slate-900">{hit.person_name}</span>
        <span className="text-[11px] text-slate-500">
          {byRole.size} distinct roles across {hit.appearances.length} cases
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1.5 mt-2">
        {[...byRole.entries()].map(([role, apps]) => {
          const danger = role === "suspect" || role === "person_of_interest";
          return (
            <div key={role}>
              <div className={
                "text-[10px] uppercase tracking-wide font-semibold mb-0.5 " +
                (danger ? "text-red-700" : "text-slate-600")
              }>
                {role.replace("_", " ")}
              </div>
              <ul className="space-y-0.5">
                {apps.map((a) => (
                  <li key={a.case_id}>
                    <button
                      type="button"
                      onClick={() => setHashPath(`${ROUTES.casePrefix}${a.case_id}`)}
                      className="text-left text-[11px] hover:underline"
                    >
                      <span className="font-mono text-slate-700">{a.case_number}</span>
                      <span className="text-slate-500"> · </span>
                      <span className="text-slate-900">{a.case_title}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </li>
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
