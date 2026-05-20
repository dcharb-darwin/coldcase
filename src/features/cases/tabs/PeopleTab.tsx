// People tab — role-grouped persons + AI extraction + cross-case lookup +
// document mention finder. Lifted out of CaseDetailPage.tsx during the
// 2026-05-20 consolidation pass to make the orchestrator file navigable.
// Behavior unchanged.

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createPerson, deletePerson, getPersonMentions, getPersonNetwork,
  listPersons, searchPersons, suggestCasePersons,
  type Person, type PersonRole, type PersonSuggestion,
} from "@/lib/api/coldcase";
import { ROUTES, setHashPath } from "@/shell/routes";


// Role palette — semantic chip colors used inside the People tab.
// Exported so the People-tab AI suggester can reuse the same palette
// without re-defining it.
export const PERSON_ROLES: { value: PersonRole; label: string; color: string }[] = [
  { value: "suspect",            label: "Suspect",            color: "bg-red-50 text-red-800 border-red-200" },
  { value: "witness",            label: "Witness",            color: "bg-blue-50 text-blue-800 border-blue-200" },
  { value: "victim",             label: "Victim",             color: "bg-amber-50 text-amber-800 border-amber-200" },
  { value: "officer",            label: "Officer",            color: "bg-indigo-50 text-indigo-800 border-indigo-200" },
  { value: "person_of_interest", label: "Person of interest", color: "bg-purple-50 text-purple-800 border-purple-200" },
  { value: "other",              label: "Other",              color: "bg-slate-100 text-slate-700 border-slate-300" },
];


// ── Per-Person affordances ────────────────────────────────────────────────


function PersonMentionsRow({ caseId, person }: { caseId: string; person: Person }) {
  // Lazy-load mentions: the substring scan over every doc is cheap, but
  // there's no reason to do it for every Person on every case render.
  const [expanded, setExpanded] = useState(false);
  const { data, isFetching } = useQuery({
    queryKey: ["person-mentions", caseId, person.id],
    queryFn: () => getPersonMentions(caseId, person.id),
    enabled: expanded,
    staleTime: 60_000,
  });
  const mentions = data?.mentions ?? [];
  const docCount = new Set(mentions.map((m) => m.document_id)).size;

  // Click a mention → bounce to the Evidence tab with the doc + line
  // pre-targeted. Reuses the cross-route citation jump.
  const jump = (filename: string, line: number) => {
    const p = new URLSearchParams({ doc: filename, line: String(line) });
    setHashPath(`${ROUTES.casePrefix}${caseId}?${p.toString()}`);
  };

  return (
    <div className="mt-1.5">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="text-[11px] text-blue-700 hover:underline"
      >
        {expanded
          ? (isFetching
              ? "Scanning documents…"
              : mentions.length > 0
                ? `− ${mentions.length} mention${mentions.length === 1 ? "" : "s"} across ${docCount} doc${docCount === 1 ? "" : "s"}`
                : "− no document mentions")
          : "+ find document mentions"}
      </button>
      {expanded && mentions.length > 0 ? (
        <ul className="mt-1.5 ml-3 pl-3 border-l-2 border-blue-200 space-y-0.5">
          {mentions.slice(0, 25).map((m, i) => (
            <li key={`${m.document_id}-${m.line}-${i}`} className="text-[11px]">
              <button
                type="button"
                onClick={() => jump(m.filename, m.line)}
                className="text-left w-full hover:bg-slate-50 rounded px-1.5 py-0.5"
                title="Jump to this line in the Evidence tab"
              >
                <span className="font-mono text-slate-500">{m.filename}</span>
                <span className="font-mono text-slate-400 mx-1">L{m.line}</span>
                <span className="text-slate-700">{m.snippet}</span>
              </button>
            </li>
          ))}
          {mentions.length > 25 ? (
            <li className="text-[10px] text-slate-500 italic px-1.5">
              + {mentions.length - 25} more — scroll the documents directly to see them all.
            </li>
          ) : null}
        </ul>
      ) : null}
    </div>
  );
}


function PersonElsewhere({ name, excludeCaseId }: { name: string; excludeCaseId: string }) {
  // Quiet by default — only renders something when there's a real
  // cross-case hit. No "loading" or "no matches" affordance.
  const [open, setOpen] = useState(false);
  const { data } = useQuery({
    queryKey: ["person-elsewhere", name, excludeCaseId],
    queryFn: () => searchPersons(name, { excludeCaseId }),
    staleTime: 60_000,
    enabled: name.trim().length >= 3,
  });
  const matches = data?.matches ?? [];
  if (matches.length === 0) return null;

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full border border-purple-200 bg-purple-50 text-purple-800 text-[11px] hover:bg-purple-100"
        title={`Appears as a Person on ${matches.length} other case${matches.length === 1 ? "" : "s"}`}
      >
        ↗ {matches.length} other case{matches.length === 1 ? "" : "s"}
      </button>
      {open ? (
        <span className="absolute left-0 top-full mt-1 z-20 bg-white border border-slate-200 rounded shadow-lg min-w-[280px] max-w-[420px]">
          <ul className="py-1">
            {matches.map((m) => (
              <li key={m.case_id}>
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    setHashPath(`${ROUTES.casePrefix}${m.case_id}`);
                  }}
                  className="w-full text-left px-3 py-1.5 hover:bg-slate-50 block"
                >
                  <div className="flex items-baseline gap-2">
                    <span className="font-mono text-xs text-slate-700">{m.case_number}</span>
                    <span className="text-[11px] text-slate-500 capitalize">{m.role.replace("_", " ")}</span>
                  </div>
                  <div className="text-xs text-slate-900 truncate">{m.case_title}</div>
                  {m.descriptor ? (
                    <div className="text-[11px] text-slate-500 truncate">{m.descriptor}</div>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        </span>
      ) : null}
    </span>
  );
}


// ── AI extraction suggester ───────────────────────────────────────────────


function PersonSuggestions({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const [run, setRun] = useState(false);
  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["person-suggestions", caseId],
    queryFn: () => suggestCasePersons(caseId),
    enabled: run,
    staleTime: 5 * 60_000,
  });
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const acceptMut = useMutation({
    // Rationale + model land in `provenance`, not in the detective's
    // `notes` field. Leaves `notes` clean for the officer's own context.
    mutationFn: (s: PersonSuggestion) => createPerson(caseId, {
      name: s.name, role: s.role, descriptor: s.descriptor,
      notes: "",
      source: "ai_suggested",
      suggested_by_model: data?.model ?? "",
      suggested_rationale: s.rationale,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case-persons", caseId] });
    },
  });

  const visible = (data?.suggestions ?? []).filter((s) => !dismissed.has(s.name));

  return (
    <div className="border border-slate-200 rounded p-3 bg-slate-50/40 mb-4">
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <div>
          <div className="text-[12px] font-semibold text-slate-900">Suggest people with AI</div>
          <div className="text-[11px] text-slate-500">
            Scan the case documents and propose named people with role + descriptor.
            You accept each individually.
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
          {data?.suggestions.length
            ? "All suggestions dismissed."
            : "No new people found in the documents."}
        </div>
      ) : null}

      {visible.length > 0 ? (
        <ul className="space-y-1.5 mt-1">
          {visible.map((s: PersonSuggestion) => {
            const roleDef = PERSON_ROLES.find((r) => r.value === s.role) || PERSON_ROLES[5]!;
            const accepted = acceptMut.isSuccess && acceptMut.variables?.name === s.name;
            return (
              <li
                key={s.name}
                className="flex items-start gap-2 p-2 bg-white border border-slate-200 rounded"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-900">{s.name}</span>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[11px] ${roleDef.color}`}>
                      {roleDef.label}
                    </span>
                  </div>
                  {s.descriptor ? (
                    <div className="text-xs text-slate-600 mt-0.5">{s.descriptor}</div>
                  ) : null}
                  {s.rationale ? (
                    <div className="text-[11px] text-slate-500 mt-1 leading-snug italic">
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
                  >
                    {accepted ? "Added ✓" : "Accept"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setDismissed((p) => new Set(p).add(s.name))}
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


// ── Tab body ──────────────────────────────────────────────────────────────


export default function PeopleTab({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const { data: persons = [], isLoading } = useQuery({
    queryKey: ["case-persons", caseId],
    queryFn: () => listPersons(caseId),
  });

  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [role, setRole] = useState<PersonRole>("witness");
  const [descriptor, setDescriptor] = useState("");
  const [notes, setNotes] = useState("");

  const invalidate = () => qc.invalidateQueries({ queryKey: ["case-persons", caseId] });
  const createMut = useMutation({
    mutationFn: () => createPerson(caseId, {
      name: name.trim(), role, descriptor: descriptor.trim(), notes: notes.trim(),
    }),
    onSuccess: () => {
      setName(""); setDescriptor(""); setNotes(""); setRole("witness"); setAdding(false);
      invalidate();
    },
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => deletePerson(caseId, id),
    onSuccess: invalidate,
  });

  // Group by role for display, preserving the declared role order.
  const grouped = useMemo(() => {
    const m = new Map<PersonRole, Person[]>();
    for (const r of PERSON_ROLES) m.set(r.value, []);
    for (const p of persons) m.get(p.role)?.push(p);
    return PERSON_ROLES.map((r) => [r, m.get(r.value) ?? []] as const)
      .filter(([, list]) => list.length > 0);
  }, [persons]);

  return (
    <div className="p-6 overflow-y-auto h-full">
      <div className="max-w-3xl">
        <div className="flex items-baseline justify-between mb-3">
          <div>
            <h2 className="text-[15px] font-semibold text-slate-900">People</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {persons.length} entry{persons.length === 1 ? "" : "ies"} ·
              <span className="ml-1">Phase B is manual entry — AI-suggested mentions land in Phase C.</span>
            </p>
          </div>
          {!adding ? (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setAdding(true)}
                className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700"
              >
                + Add person
              </button>
            </div>
          ) : null}
        </div>

        <PersonSuggestions caseId={caseId} />


        {adding ? (
          <div className="border border-slate-200 rounded p-3 mb-4 bg-slate-50/50 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-[11px] text-slate-600">Name</span>
                <input
                  className="mt-0.5 w-full border border-slate-300 rounded px-2 py-1 text-sm"
                  value={name} onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. John Doe"
                  autoFocus
                />
              </label>
              <label className="block">
                <span className="text-[11px] text-slate-600">Role</span>
                <select
                  className="mt-0.5 w-full border border-slate-300 rounded px-2 py-1 text-sm bg-white"
                  value={role} onChange={(e) => setRole(e.target.value as PersonRole)}
                >
                  {PERSON_ROLES.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
              </label>
            </div>
            <label className="block">
              <span className="text-[11px] text-slate-600">Descriptor (optional)</span>
              <input
                className="mt-0.5 w-full border border-slate-300 rounded px-2 py-1 text-sm"
                value={descriptor} onChange={(e) => setDescriptor(e.target.value)}
                placeholder="DOB, alias, badge #, address — whatever makes them identifiable"
              />
            </label>
            <label className="block">
              <span className="text-[11px] text-slate-600">Notes (optional)</span>
              <textarea
                className="mt-0.5 w-full border border-slate-300 rounded px-2 py-1 text-sm"
                rows={3}
                value={notes} onChange={(e) => setNotes(e.target.value)}
                placeholder="Cite the document/source. AI-extracted mention linking comes in Phase C."
              />
            </label>
            {createMut.error ? (
              <div className="text-xs text-red-700">{(createMut.error as Error).message}</div>
            ) : null}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => { setAdding(false); setName(""); }}
                className="px-3 py-1 text-sm rounded border border-slate-300 hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={createMut.isPending || !name.trim()}
                onClick={() => createMut.mutate()}
                className="px-3 py-1 text-sm rounded bg-blue-600 text-white disabled:opacity-50"
              >
                {createMut.isPending ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        ) : null}

        {isLoading ? (
          <div className="text-sm text-slate-500">Loading people…</div>
        ) : persons.length === 0 ? (
          <div className="border border-dashed border-slate-300 rounded p-8 text-center text-sm text-slate-500">
            No people on this case yet. Add the suspects, witnesses, victims,
            and officers of record so they're a first-class part of the case file.
          </div>
        ) : (
          <div className="space-y-5">
            {grouped.map(([roleDef, list]) => (
              <section key={roleDef.value}>
                <h3 className="text-[12px] font-semibold text-slate-700 mb-2 flex items-center gap-2">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[11px] ${roleDef.color}`}>
                    {roleDef.label}
                  </span>
                  <span className="text-slate-500 font-normal">({list.length})</span>
                </h3>
                <ul className="space-y-1.5">
                  {list.map((p) => (
                    <li key={p.id} className="border border-slate-200 rounded p-2.5 bg-white hover:border-slate-300 group">
                      <div className="flex items-baseline justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-slate-900">{p.name}</span>
                            {p.provenance?.source === "ai_suggested" ? (
                              <span
                                className="inline-flex items-center px-1.5 py-0.5 rounded-full border border-purple-200 bg-purple-50 text-purple-800 text-[10px] uppercase tracking-wide font-medium"
                                title={
                                  `Accepted from AI suggestion${p.provenance.suggested_by_model ? ` · ${p.provenance.suggested_by_model}` : ""}`
                                  + (p.provenance.suggested_rationale ? `\n\n${p.provenance.suggested_rationale}` : "")
                                }
                              >
                                AI
                              </span>
                            ) : null}
                            <PersonElsewhere name={p.name} excludeCaseId={caseId} />
                          </div>
                          {p.descriptor ? (
                            <div className="text-xs text-slate-600 mt-0.5">{p.descriptor}</div>
                          ) : null}
                          {p.notes ? (
                            <div className="text-xs text-slate-500 mt-1 whitespace-pre-wrap leading-relaxed">{p.notes}</div>
                          ) : null}
                          {p.provenance?.source === "ai_suggested" && p.provenance.suggested_rationale ? (
                            <div className="text-[11px] text-purple-700 italic mt-1 leading-snug">
                              {p.provenance.suggested_rationale}
                            </div>
                          ) : null}
                          <PersonMentionsRow caseId={caseId} person={p} />
                        </div>
                        <button
                          type="button"
                          onClick={() => deleteMut.mutate(p.id)}
                          className="opacity-0 group-hover:opacity-100 text-xs text-slate-400 hover:text-red-700 transition-opacity"
                          title="Remove this person"
                        >
                          remove
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
