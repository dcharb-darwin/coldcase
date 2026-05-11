import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listAuditEvents, type AuditEvent } from "@/lib/api/coldcase";

const EVENT_TYPES = [
  "", "case.created", "case.updated", "case.closed",
  "document.registered", "media.registered",
  "conversation.started", "message.user", "message.assistant",
  "report.drafted", "report.edited", "report.signed", "report.exported",
  "retention.changed", "vendor.access",
];

function eventBadge(t: string): string {
  if (t.startsWith("report.")) return "bg-emerald-100 text-emerald-800";
  if (t.startsWith("message.")) return "bg-blue-100 text-blue-800";
  if (t.startsWith("case.")) return "bg-slate-200 text-slate-700";
  if (t.startsWith("vendor.")) return "bg-red-100 text-red-800";
  return "bg-amber-100 text-amber-800";
}

export default function AuditPage() {
  const [eventType, setEventType] = useState("");
  const [caseId, setCaseId] = useState("");
  const [userId, setUserId] = useState("");

  const filter = useMemo(() => ({
    event_type: eventType || undefined,
    case_id: caseId || undefined,
    user_id: userId || undefined,
    limit: 200,
  }), [eventType, caseId, userId]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["audit", "events", filter],
    queryFn: () => listAuditEvents(filter),
  });

  const events: AuditEvent[] = data?.events ?? [];

  return (
    <div className="p-6">
      <header className="mb-5">
        <h1 className="text-2xl font-semibold">Audit trail</h1>
        <p className="text-sm text-slate-500 mt-1">
          §13663(c) chain of custody. Filter by case, user, or event type. The
          full prompt chain for any single report is available on the report
          itself.
        </p>
      </header>

      <div className="flex flex-wrap gap-3 mb-4">
        <label className="text-sm">
          <span className="text-xs text-slate-500 block">Event type</span>
          <select
            className="border border-slate-300 rounded px-2 py-1 text-sm w-56"
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
          >
            {EVENT_TYPES.map((t) => (
              <option key={t} value={t}>{t || "(any)"}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="text-xs text-slate-500 block">Case ID</span>
          <input
            className="border border-slate-300 rounded px-2 py-1 text-sm w-64 font-mono text-xs"
            value={caseId}
            onChange={(e) => setCaseId(e.target.value)}
            placeholder="(any)"
          />
        </label>
        <label className="text-sm">
          <span className="text-xs text-slate-500 block">User ID</span>
          <input
            className="border border-slate-300 rounded px-2 py-1 text-sm w-48 font-mono text-xs"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="(any)"
          />
        </label>
      </div>

      {isLoading ? <div className="text-slate-500">Loading…</div> : null}
      {error ? <div className="text-red-700">{(error as Error).message}</div> : null}

      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-600 text-xs uppercase tracking-wide">
            <tr>
              <th className="px-3 py-2">When</th>
              <th className="px-3 py-2">Event</th>
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Summary</th>
              <th className="px-3 py-2">Refs</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} className="border-t border-slate-100 align-top">
                <td className="px-3 py-2 text-xs whitespace-nowrap text-slate-600">
                  {e.timestamp ? new Date(e.timestamp).toLocaleString() : "—"}
                </td>
                <td className="px-3 py-2">
                  <span className={`inline-flex px-2 py-0.5 rounded text-xs font-mono ${eventBadge(e.event_type)}`}>
                    {e.event_type}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs font-mono">{e.user_display || e.user_id}</td>
                <td className="px-3 py-2 text-xs text-slate-700">{e.summary}</td>
                <td className="px-3 py-2 text-[10px] font-mono text-slate-500">
                  {e.case_id ? <div>case: {e.case_id.slice(-8)}</div> : null}
                  {e.report_id ? <div>report: {e.report_id.slice(-8)}</div> : null}
                  {e.message_id ? <div>msg: {e.message_id.slice(-8)}</div> : null}
                </td>
              </tr>
            ))}
            {events.length === 0 && !isLoading ? (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-slate-400 text-sm">No events match.</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <div className="mt-2 text-xs text-slate-500">
        Showing {events.length} event(s). Use the filters above to narrow.
      </div>
    </div>
  );
}
