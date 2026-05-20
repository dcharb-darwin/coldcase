import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

// Test-fixture case numbers we hide from the list by default so the
// detective doesn't open the app and see a screen full of smoke-test rows.
// The toggle on the toolbar restores them for QA work.
const TEST_FIXTURE_PREFIX = /^(SMOKE|F\d|CC-SMOKE)/i;
import {
  createCase,
  listCases,
  listTags,
  seedCivilRightsCases,
  seedSyntheticDemo,
  type CaseClassification,
  type Case as CaseT,
} from "@/lib/api/coldcase";
import { caseKeys } from "../queryKeys";
import { ROUTES, setHashPath } from "@/shell/routes";
import { TagChip } from "../components/TagChips";

const CLASSIFICATIONS: { value: CaseClassification; label: string }[] = [
  { value: "homicide", label: "Homicide" },
  { value: "robbery", label: "Robbery" },
  { value: "assault", label: "Assault" },
  { value: "burglary", label: "Burglary" },
  { value: "sexual_assault", label: "Sexual assault" },
  { value: "missing_person", label: "Missing person" },
  { value: "other", label: "Other" },
];

function StatusBadge({ status }: { status: CaseT["status"] }) {
  const map: Record<CaseT["status"], string> = {
    open: "bg-blue-100 text-blue-800",
    active: "bg-emerald-100 text-emerald-800",
    closed: "bg-slate-200 text-slate-700",
    reopened: "bg-amber-100 text-amber-800",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${map[status]}`}>
      {status}
    </span>
  );
}

function ClassificationBadge({ value }: { value: CaseT["classification"] }) {
  const danger = value === "homicide" || value === "sexual_assault";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${
        danger ? "bg-red-100 text-red-800" : "bg-slate-100 text-slate-700"
      }`}
    >
      {value.replace("_", " ")}
    </span>
  );
}

function CreateCaseModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [caseNumber, setCaseNumber] = useState(() => `CC-${new Date().getFullYear()}-${Math.floor(Math.random() * 9000 + 1000)}`);
  const [title, setTitle] = useState("");
  const [classification, setClassification] = useState<CaseClassification>("other");
  const [description, setDescription] = useState("");

  const mutation = useMutation({
    mutationFn: () => createCase({ case_number: caseNumber, title, classification, description }),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: caseKeys.all });
      onClose();
      setHashPath(`${ROUTES.casePrefix}${created.id}`);
    },
  });

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold mb-4">New case</h2>
        <div className="space-y-3">
          <label className="block">
            <span className="text-sm text-slate-600">Case number</span>
            <input
              className="mt-1 w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
              value={caseNumber}
              onChange={(e) => setCaseNumber(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-600">Title</span>
            <input
              className="mt-1 w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. 1987 Riverside Park homicide"
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-600">Classification</span>
            <select
              className="mt-1 w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
              value={classification}
              onChange={(e) => setClassification(e.target.value as CaseClassification)}
            >
              {CLASSIFICATIONS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
            {classification === "homicide" && (
              <span className="block mt-1 text-xs text-amber-700">
                Homicide → retention will default to <strong>indefinite</strong> per Penal Code §13663(b).
              </span>
            )}
          </label>
          <label className="block">
            <span className="text-sm text-slate-600">Description</span>
            <textarea
              className="mt-1 w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>
        </div>
        {mutation.error ? (
          <div className="mt-3 text-sm text-red-700">
            {(mutation.error as Error).message}
          </div>
        ) : null}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-sm rounded border border-slate-300"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={mutation.isPending || !title.trim()}
            onClick={() => mutation.mutate()}
            className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white disabled:opacity-50"
          >
            {mutation.isPending ? "Creating…" : "Create case"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CaseListPage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [classFilter, setClassFilter] = useState<"" | CaseClassification>("");
  const [showTestCases, setShowTestCases] = useState(false);
  // Multi-tag AND filter: a case must carry every selected tag slug to show.
  const [activeTagSlugs, setActiveTagSlugs] = useState<string[]>([]);

  const { data: cases = [], isLoading, error } = useQuery({
    queryKey: caseKeys.list(),
    queryFn: () => listCases(),
    refetchOnMount: "always",
    staleTime: 0,
  });

  const { data: vocab = [] } = useQuery({
    queryKey: ["tags", "vocab"],
    queryFn: listTags,
    staleTime: 5 * 60_000,
  });

  // Filter chips show only tags that are actually in use on the current set
  // of cases — keeps the row from advertising tags that would return zero
  // matches. Combines vocabulary (user tags) with system tags pulled
  // straight from the cases (which are not in `vocab`).
  const inUseTags = useMemo(() => {
    const seen = new Map<string, { slug: string; label: string; kind: "user" | "system" }>();
    for (const c of cases) {
      for (const t of c.tags ?? []) {
        if (!seen.has(t.slug)) {
          seen.set(t.slug, { slug: t.slug, label: t.label, kind: t.kind });
        }
      }
    }
    // Order: user tags first (alpha), then system tags (alpha).
    return [...seen.values()].sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === "user" ? -1 : 1;
      return a.label.localeCompare(b.label);
    });
  }, [cases]);
  // Vocab is still useful for descriptions in tooltips on the filter chips.
  const vocabBySlug = useMemo(() => {
    const m = new Map<string, string>();
    vocab.forEach((t) => m.set(t.slug, t.description));
    return m;
  }, [vocab]);

  const toggleTag = (slug: string) => setActiveTagSlugs((prev) =>
    prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug],
  );

  const filteredCases = useMemo(() => {
    const q = query.trim().toLowerCase();
    return cases.filter((c) => {
      if (!showTestCases && TEST_FIXTURE_PREFIX.test(c.case_number)) return false;
      if (classFilter && c.classification !== classFilter) return false;
      if (q && !c.case_number.toLowerCase().includes(q) && !c.title.toLowerCase().includes(q)) return false;
      if (activeTagSlugs.length) {
        const have = new Set((c.tags ?? []).map((t) => t.slug));
        if (!activeTagSlugs.every((s) => have.has(s))) return false;
      }
      return true;
    });
  }, [cases, query, classFilter, showTestCases, activeTagSlugs]);
  const hiddenCount = cases.length - filteredCases.length;

  const seedMutation = useMutation({
    mutationFn: () => seedSyntheticDemo(),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: caseKeys.all });
      setHashPath(`${ROUTES.casePrefix}${res.case_id}`);
    },
  });

  const civilRightsMutation = useMutation({
    mutationFn: () => seedCivilRightsCases(),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: caseKeys.all });
      const first = res.cases[0];
      if (first) setHashPath(`${ROUTES.casePrefix}${first.case_id}`);
    },
  });

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-2xl font-semibold">Cold cases</h1>
          <p className="text-sm text-slate-500 mt-1">
            Every AI-assisted interaction here is logged under California Penal Code §13663.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => seedMutation.mutate()}
            disabled={seedMutation.isPending}
            className="px-3 py-1.5 text-sm rounded border border-slate-300 hover:bg-slate-50 disabled:opacity-50"
            title="Create the synthetic 1992 Riverside Park homicide demo case with 4 PDFs and 2 media inputs."
          >
            {seedMutation.isPending ? "Seeding…" : "🧪 Load demo case"}
          </button>
          <button
            type="button"
            onClick={() => civilRightsMutation.mutate()}
            disabled={civilRightsMutation.isPending}
            className="px-3 py-1.5 text-sm rounded border border-slate-300 hover:bg-slate-50 disabled:opacity-50"
            title="Download 3 real public-domain federal investigative case files (Civil Rights Cold Case Records Review Board)."
          >
            {civilRightsMutation.isPending ? "Downloading PDFs…" : "📜 Load real cold cases"}
          </button>
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700"
          >
            + New case
          </button>
        </div>
      </div>

      {isLoading ? <div className="text-slate-500">Loading cases…</div> : null}
      {error ? <div className="text-red-700">{(error as Error).message}</div> : null}

      {cases.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 mb-3 text-sm">
          <input
            type="search"
            placeholder="Search case number or title…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 min-w-[220px] max-w-md border border-slate-300 rounded px-3 py-1.5"
          />
          <select
            value={classFilter}
            onChange={(e) => setClassFilter(e.target.value as "" | CaseClassification)}
            className="border border-slate-300 rounded px-2 py-1.5 bg-white"
          >
            <option value="">All classifications</option>
            {CLASSIFICATIONS.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 text-xs text-slate-700 ml-1">
            <input
              type="checkbox"
              checked={showTestCases}
              onChange={(e) => setShowTestCases(e.target.checked)}
            />
            <span>Show test fixtures</span>
          </label>
          <span className="ml-auto text-xs text-slate-500">
            {filteredCases.length} of {cases.length} cases
            {hiddenCount > 0 ? ` · ${hiddenCount} hidden by filter` : ""}
          </span>
        </div>
      ) : null}

      {inUseTags.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5 mb-3">
          <span className="text-[11px] text-slate-500 mr-1">Filter by tag:</span>
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

      {!isLoading && cases.length === 0 ? (
        <div className="border border-dashed border-slate-300 rounded-lg p-10 text-center text-slate-500">
          No cases yet. Create one to begin.
        </div>
      ) : null}

      {cases.length > 0 ? (
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-600 text-xs uppercase tracking-wide">
              <tr>
                <th className="px-4 py-2">Case number</th>
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">Classification</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Retention</th>
                <th className="px-4 py-2">Last activity</th>
              </tr>
            </thead>
            <tbody>
              {filteredCases.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-slate-500">
                    No cases match the current filter.
                  </td>
                </tr>
              ) : filteredCases.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => setHashPath(`${ROUTES.casePrefix}${c.id}`)}
                  className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                >
                  <td className="px-4 py-2 font-mono text-xs align-top">{c.case_number}</td>
                  <td className="px-4 py-2 align-top">
                    <div>{c.title}</div>
                    {c.tags && c.tags.length > 0 ? (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {c.tags.map((t) => (
                          <TagChip key={t.id} tag={t} />
                        ))}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-4 py-2 align-top"><ClassificationBadge value={c.classification} /></td>
                  <td className="px-4 py-2"><StatusBadge status={c.status} /></td>
                  <td className="px-4 py-2 text-xs text-slate-600">{c.retention_policy}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">
                    {c.last_activity_at ? new Date(c.last_activity_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <CreateCaseModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}
