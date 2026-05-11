import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createCase,
  listCases,
  seedSyntheticDemo,
  type CaseClassification,
  type Case as CaseT,
} from "@/lib/api/coldcase";
import { caseKeys } from "../queryKeys";
import { ROUTES, setHashPath } from "@/shell/routes";

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
  const { data: cases = [], isLoading, error } = useQuery({
    queryKey: caseKeys.list(),
    queryFn: listCases,
    refetchOnMount: "always",
    staleTime: 0,
  });

  const seedMutation = useMutation({
    mutationFn: () => seedSyntheticDemo(),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: caseKeys.all });
      setHashPath(`${ROUTES.casePrefix}${res.case_id}`);
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
            onClick={() => setCreateOpen(true)}
            className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700"
          >
            + New case
          </button>
        </div>
      </div>

      {isLoading ? <div className="text-slate-500">Loading cases…</div> : null}
      {error ? <div className="text-red-700">{(error as Error).message}</div> : null}

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
              {cases.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => setHashPath(`${ROUTES.casePrefix}${c.id}`)}
                  className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                >
                  <td className="px-4 py-2 font-mono text-xs">{c.case_number}</td>
                  <td className="px-4 py-2">{c.title}</td>
                  <td className="px-4 py-2"><ClassificationBadge value={c.classification} /></td>
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
