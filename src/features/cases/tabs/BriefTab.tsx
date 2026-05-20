import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  assignTag,
  createNote,
  getCaseConnections,
  getPersonNetwork,
  getSimilarCases,
  suggestCaseTags,
  suggestNextSteps,
  type Case as CaseT,
  type ConnectionNode,
  type Document,
  type MediaInput,
  type NextStepSuggestion,
  type RelatedPerson,
  type Report,
  type TagSuggestion,
} from "@/lib/api/coldcase";
import { caseKeys } from "../queryKeys";
import NotesPanel from "../components/NotesPanel";
import { TagChip } from "../components/TagChips";
import { ROUTES, setHashPath } from "@/shell/routes";

export default function BriefTab({
  c, documents, media, reports,
}: { c: CaseT; documents: Document[]; media: MediaInput[]; reports: Report[] }) {
  const signedReports = reports.filter((r) => r.status === "signed" || r.status === "exported");
  const draftReports = reports.filter((r) => r.status === "draft");
  const lastSigned = signedReports
    .map((r) => r.signed_at)
    .filter(Boolean)
    .sort()
    .at(-1) ?? null;
  const ocrDocs = documents.length;

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

        <section>
          <h2 className="text-[15px] font-semibold text-slate-900 mb-3">Key dates</h2>
          <ol className="border-l-2 border-slate-200 pl-4 space-y-2.5 text-sm">
            <DateRow label="Incident occurred" value={c.date_of_incident} hint="§13663 incident_date" />
            <DateRow label="Case opened" value={c.created_at} />
            <DateRow label="Latest report signed" value={lastSigned} tone="good" />
            <DateRow label="Case closed" value={c.closed_at} tone="muted" />
          </ol>
        </section>

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

        <section className="border border-slate-200 rounded p-3 bg-slate-50/30">
          <NotesPanel caseId={c.id} subjectKind="case" subjectId={c.id} />
        </section>

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
  const [run, setRun] = useState(false);
  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["tag-suggestions", caseId],
    queryFn: () => suggestCaseTags(caseId),
    enabled: run,
    staleTime: 5 * 60_000,
  });
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

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
  const { data, isLoading, error } = useQuery({
    queryKey: ["case-connections", caseId],
    queryFn: () => getCaseConnections(caseId),
    staleTime: 60_000,
  });

  if (isLoading || error || !data) return null;

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
  const [expanded, setExpanded] = useState(false);
  const { data: network, isFetching: networkLoading } = useQuery({
    queryKey: ["person-network", person.name, caseId],
    queryFn: () => getPersonNetwork(person.name ?? "", { excludeCaseId: caseId }),
    enabled: expanded && Boolean(person.name),
    staleTime: 60_000,
  });

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
