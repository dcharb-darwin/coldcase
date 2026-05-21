import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createTimelineEntry,
  deleteTimelineEntry,
  listAuditEvents,
  listTimelineEntries,
  suggestTimelineEntries,
  type AuditEvent,
  type TimelineEntry as TimelineEntryT,
  type TimelineEntrySuggestion,
} from "@/lib/api/coldcase";

export default function TimelineTab({ caseId }: { caseId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["case-timeline", caseId],
    queryFn: () => listAuditEvents({ case_id: caseId, limit: 200 }),
    staleTime: 10_000,
  });

  const events = data?.events ?? [];

  const grouped = useMemo(() => {
    const byDay = new Map<string, AuditEvent[]>();
    for (const e of events) {
      const day = e.timestamp ? new Date(e.timestamp).toISOString().slice(0, 10) : "unknown";
      byDay.set(day, [...(byDay.get(day) ?? []), e]);
    }
    return [...byDay.entries()].sort(([a], [b]) => b.localeCompare(a));
  }, [events]);

  if (isLoading) return <div className="p-6 text-sm text-slate-500">Loading timeline…</div>;
  if (error) return <div className="p-6 text-sm text-red-700">{(error as Error).message}</div>;
  if (events.length === 0) {
    return (
      <div className="p-6 text-sm text-slate-500 max-w-3xl">
        No activity on this case yet. Events appear here as documents are registered,
        chat messages are sent, and reports are signed.
      </div>
    );
  }

  return (
    <div className="p-6 overflow-y-auto h-full">
      <div className="max-w-3xl space-y-6">
        <CaseEventsSection caseId={caseId} />

        <section>
          <h2 className="text-[15px] font-semibold text-slate-900 mb-1">Activity log</h2>
          <p className="text-xs text-slate-500 mb-4">
            Every action on this case, chronologically. {events.length} event{events.length === 1 ? "" : "s"}.
          </p>
          {grouped.map(([day, list]) => (
            <section key={day} className="mb-6">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2 sticky top-0 bg-white py-1">
                {day === "unknown" ? "Unknown date" : formatDay(day)}
              </h3>
              <ol className="border-l-2 border-slate-200 pl-4 space-y-2">
                {list.map((e) => <TimelineRow key={e.id} event={e} />)}
              </ol>
            </section>
          ))}
        </section>
      </div>
    </div>
  );
}

function CaseEventsSection({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const { data: entries = [] } = useQuery({
    queryKey: ["case-timeline-entries", caseId],
    queryFn: () => listTimelineEntries(caseId),
  });
  const [adding, setAdding] = useState(false);
  const [occurred, setOccurred] = useState("");
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");

  const invalidate = () => qc.invalidateQueries({ queryKey: ["case-timeline-entries", caseId] });
  const addMut = useMutation({
    mutationFn: () => createTimelineEntry(caseId, {
      occurred_at: occurred.trim(), label: label.trim(), notes: notes.trim(),
    }),
    onSuccess: () => { setOccurred(""); setLabel(""); setNotes(""); setAdding(false); invalidate(); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteTimelineEntry(caseId, id),
    onSuccess: invalidate,
  });

  return (
    <section>
      <div className="flex items-baseline justify-between mb-2">
        <div>
          <h2 className="text-[15px] font-semibold text-slate-900">Case events</h2>
          <p className="text-xs text-slate-500">
            The detective's chronology of what happened — distinct from the
            system activity log below. {entries.length} entr{entries.length === 1 ? "y" : "ies"}.
          </p>
        </div>
        {!adding ? (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="px-2.5 py-1 text-xs rounded border border-slate-300 hover:bg-slate-50"
          >
            + Add event
          </button>
        ) : null}
      </div>

      <TimelineSuggestions caseId={caseId} existingLabels={new Set(entries.map((e) => e.label.toLowerCase()))} onAccepted={invalidate} />

      {adding ? (
        <div className="border border-slate-200 rounded p-3 mb-3 bg-slate-50/60 space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <label className="block">
              <span className="text-[11px] text-slate-600">When (free form)</span>
              <input
                className="mt-0.5 w-full border border-slate-300 rounded px-2 py-1 text-sm"
                value={occurred} onChange={(e) => setOccurred(e.target.value)}
                placeholder="e.g. 1945-08-15 17:00 or circa Aug 1945"
                autoFocus
              />
            </label>
            <label className="block col-span-2">
              <span className="text-[11px] text-slate-600">Label</span>
              <input
                className="mt-0.5 w-full border border-slate-300 rounded px-2 py-1 text-sm"
                value={label} onChange={(e) => setLabel(e.target.value)}
                placeholder="One short phrase describing what happened"
              />
            </label>
          </div>
          <label className="block">
            <span className="text-[11px] text-slate-600">Notes (optional)</span>
            <textarea
              className="mt-0.5 w-full border border-slate-300 rounded px-2 py-1 text-sm"
              rows={2}
              value={notes} onChange={(e) => setNotes(e.target.value)}
            />
          </label>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => { setAdding(false); setOccurred(""); setLabel(""); setNotes(""); }}
              className="px-3 py-1 text-sm rounded border border-slate-300 hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={addMut.isPending || !occurred.trim() || !label.trim()}
              onClick={() => addMut.mutate()}
              className="px-3 py-1 text-sm rounded bg-blue-600 text-white disabled:opacity-50"
            >
              {addMut.isPending ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      ) : null}

      {entries.length === 0 ? (
        <div className="border border-dashed border-slate-300 rounded p-6 text-center text-xs text-slate-500">
          No events yet. Add the dated facts of the case so you have a chronological
          narrative — or click "Suggest events" to extract them from the documents.
        </div>
      ) : (
        <ol className="border-l-2 border-emerald-200 pl-4 space-y-2">
          {entries.map((e) => <CaseEventRow key={e.id} entry={e} onDelete={() => deleteMut.mutate(e.id)} />)}
        </ol>
      )}
    </section>
  );
}

function CaseEventRow({ entry, onDelete }: { entry: TimelineEntryT; onDelete: () => void }) {
  const isAi = entry.source === "ai_suggested";
  return (
    <li className="relative group">
      <span className={`absolute -left-[22px] top-1.5 w-3 h-3 rounded-full ring-2 ring-white ${isAi ? "bg-purple-500" : "bg-emerald-500"}`} />
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="text-xs font-mono text-slate-600 shrink-0">{entry.occurred_at}</span>
            <span className="text-sm text-slate-900">{entry.label}</span>
            {isAi ? (
              <span className="text-[10px] uppercase tracking-wide text-purple-700">AI</span>
            ) : null}
          </div>
          {entry.notes ? (
            <div className="text-xs text-slate-600 mt-0.5 leading-relaxed">{entry.notes}</div>
          ) : null}
          {isAi && entry.rationale ? (
            <div className="text-[11px] text-purple-700 italic mt-0.5">{entry.rationale}</div>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onDelete}
          className="opacity-0 group-hover:opacity-100 text-[11px] text-slate-400 hover:text-red-700 shrink-0"
          title="Remove this event"
        >
          remove
        </button>
      </div>
    </li>
  );
}

function TimelineSuggestions({
  caseId, existingLabels, onAccepted,
}: { caseId: string; existingLabels: Set<string>; onAccepted: () => void }) {
  const [run, setRun] = useState(false);
  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["timeline-suggestions", caseId],
    queryFn: () => suggestTimelineEntries(caseId),
    enabled: run,
    staleTime: 5 * 60_000,
  });
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const acceptMut = useMutation({
    mutationFn: (s: TimelineEntrySuggestion) => createTimelineEntry(caseId, {
      occurred_at: s.occurred_at, label: s.label, notes: s.notes,
      source_document_id: s.source_document_id, rationale: s.rationale,
      source: "ai_suggested",
    }),
    onSuccess: onAccepted,
  });

  const visible = (data?.suggestions ?? []).filter(
    (s) => !dismissed.has(s.label) && !existingLabels.has(s.label.toLowerCase()),
  );

  return (
    <div className="border border-slate-200 rounded p-3 bg-slate-50/40 mb-3">
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <div>
          <div className="text-[12px] font-semibold text-slate-900">Suggest events with AI</div>
          <div className="text-[11px] text-slate-500">
            Pull dated events from the case documents. You accept each individually.
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
          {data?.suggestions.length ? "All suggestions handled." : "No new events found."}
        </div>
      ) : null}

      {visible.length > 0 ? (
        <ul className="space-y-1.5 mt-1">
          {visible.map((s: TimelineEntrySuggestion) => {
            const accepted = acceptMut.isSuccess && acceptMut.variables?.label === s.label;
            return (
              <li key={s.label} className="flex items-start gap-2 p-2 bg-white border border-slate-200 rounded">
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className="text-xs font-mono text-slate-600">{s.occurred_at}</span>
                    <span className="text-sm text-slate-900 font-medium">{s.label}</span>
                  </div>
                  {s.notes ? <div className="text-xs text-slate-600 mt-0.5">{s.notes}</div> : null}
                  {s.rationale ? (
                    <div className="text-[11px] text-purple-700 italic mt-0.5">{s.rationale}</div>
                  ) : null}
                  {s.source_document ? (
                    <div className="text-[10px] text-slate-400 mt-0.5 font-mono">{s.source_document}</div>
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
                    onClick={() => setDismissed((p) => new Set(p).add(s.label))}
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

function formatDay(day: string): string {
  const d = new Date(`${day}T00:00:00`);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diffDays = Math.round((today.getTime() - d.getTime()) / 86_400_000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "short", year: "numeric", month: "short", day: "numeric" });
}

const TIMELINE_COLORS: Record<string, string> = {
  "case":         "bg-slate-400",
  "document":     "bg-blue-500",
  "media":        "bg-indigo-500",
  "conversation": "bg-blue-400",
  "message":      "bg-blue-400",
  "report":       "bg-emerald-500",
  "approval":     "bg-emerald-600",
  "retention":    "bg-amber-500",
  "vendor":       "bg-red-500",
  "purge":        "bg-red-500",
  "first_draft":  "bg-red-500",
};

export function timelineColorFor(eventType: string): string {
  const prefix = eventType.split(".")[0] ?? "";
  return TIMELINE_COLORS[prefix] ?? "bg-slate-400";
}

function TimelineRow({ event }: { event: AuditEvent }) {
  const time = event.timestamp ? new Date(event.timestamp) : null;
  const dotCls = timelineColorFor(event.event_type);
  return (
    <li className="relative pb-1.5">
      <span
        className={`absolute -left-[22px] top-1.5 w-3 h-3 rounded-full ring-2 ring-white ${dotCls}`}
        title={event.event_type}
      />
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-sm text-slate-800">{event.summary || event.event_type}</div>
          <div className="text-[11px] text-slate-500 mt-0.5 flex flex-wrap gap-x-2">
            <span className="font-mono">{event.event_type}</span>
            {event.user_display ? <span>· {event.user_display}</span> : null}
          </div>
        </div>
        <span className="text-[11px] text-slate-500 shrink-0">
          {time ? time.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : ""}
        </span>
      </div>
    </li>
  );
}
