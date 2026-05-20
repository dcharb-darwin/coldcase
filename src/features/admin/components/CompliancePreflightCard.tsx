import { useQuery } from "@tanstack/react-query";
import { getCompliancePreflight } from "@/lib/api/coldcase";

/**
 * Surfaces /admin/compliance/preflight as a green/red checklist at the top of
 * the admin section. The deployment runbook should refuse a pilot go-live
 * unless every check passes — this card is the place a records officer
 * confirms that quickly without ssh'ing to the box.
 *
 * Matches docs/legal/compliance-status.md punch-list ordering.
 */
export default function CompliancePreflightCard() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["admin", "compliance-preflight"],
    queryFn: getCompliancePreflight,
    // Cheap call; let the user trigger refreshes manually so the card is a
    // snapshot they can point at, not a live-updating thing.
    staleTime: 60_000,
  });

  return (
    <section className="border border-slate-200 rounded bg-white p-4">
      <header className="flex items-center justify-between gap-3 mb-3">
        <div>
          <h2 className="text-[15px] font-semibold text-slate-900">
            §13663 deployment preflight
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Every check must pass before any agency runs an AI-assisted official report in
            production. Refresh after changing env / config.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="px-2.5 py-1 text-xs rounded border border-slate-300 hover:bg-slate-100 disabled:opacity-50"
        >
          {isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {isLoading ? (
        <div className="text-sm text-slate-500">Loading preflight…</div>
      ) : error ? (
        <div className="text-sm text-red-700">{(error as Error).message}</div>
      ) : !data ? (
        <div className="text-sm text-slate-500">No preflight data.</div>
      ) : (
        <>
          <ReadyBanner
            ready={data.ready}
            environment={data.environment}
            failedCount={data.failed_check_ids.length}
          />
          <ul className="mt-3 space-y-1.5">
            {data.checks.map((check) => (
              <li
                key={check.id}
                className={
                  "flex items-start gap-2 text-sm p-2 rounded border " +
                  (check.passed
                    ? "border-emerald-200 bg-emerald-50"
                    : "border-red-200 bg-red-50")
                }
              >
                <span
                  className={
                    "shrink-0 w-5 h-5 flex items-center justify-center rounded-full text-xs font-bold " +
                    (check.passed
                      ? "bg-emerald-600 text-white"
                      : "bg-red-600 text-white")
                  }
                  aria-label={check.passed ? "passed" : "failed"}
                >
                  {check.passed ? "✓" : "!"}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-slate-900">{check.label}</div>
                  <div className="text-xs text-slate-600 mt-0.5">{check.detail}</div>
                </div>
                <span className="shrink-0 text-[10px] font-mono text-slate-500">
                  {check.statute_ref}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function ReadyBanner({
  ready, environment, failedCount,
}: { ready: boolean; environment: string; failedCount: number }) {
  if (ready) {
    return (
      <div className="px-3 py-2 rounded border border-emerald-200 bg-emerald-50 text-emerald-900 text-sm">
        <strong>Ready</strong> — all checks passed in <code>{environment}</code>.
      </div>
    );
  }
  return (
    <div className="px-3 py-2 rounded border border-red-200 bg-red-50 text-red-900 text-sm">
      <strong>Not ready</strong> — {failedCount} check
      {failedCount === 1 ? "" : "s"} failing in <code>{environment}</code>. Resolve before
      pilot go-live.
    </div>
  );
}
