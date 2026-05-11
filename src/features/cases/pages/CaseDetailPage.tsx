import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getCase,
  getDocumentText,
  getDocumentTextStatus,
  listConversations,
  listReportsForCase,
  registerDocument,
  registerMedia,
  startConversation,
  type Document,
  type DocumentTextStatus,
  type MediaInput,
  type Message,
  type Report,
} from "@/lib/api/coldcase";
import { caseKeys } from "../queryKeys";
import ChatPanel from "../components/ChatPanel";
import ReportDrawer from "../components/ReportDrawer";

type DrawerState =
  | { kind: "closed" }
  | { kind: "promote"; sourceMessage: Message }
  | { kind: "report"; reportId: string };

interface CaseDetailPageProps {
  caseId: string;
}

export default function CaseDetailPage({ caseId }: CaseDetailPageProps) {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: caseKeys.detail(caseId),
    queryFn: () => getCase(caseId),
  });
  const { data: reports = [] } = useQuery({
    queryKey: caseKeys.reports(caseId),
    queryFn: () => listReportsForCase(caseId),
  });
  const { data: convs = [] } = useQuery({
    queryKey: caseKeys.conversations(caseId),
    queryFn: () => listConversations(caseId),
  });

  const [drawer, setDrawer] = useState<DrawerState>({ kind: "closed" });
  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  const [highlightLine, setHighlightLine] = useState<number | null>(null);

  // Citation handler — invoked by clickable chips in chat messages and report
  // text. Switches to the cited document and highlights the cited line.
  const handleCitationClick = useCallback((filename: string, line: number) => {
    if (!data) return;
    const target = data.documents.find((d) => d.original_filename === filename);
    if (!target) return;
    setActiveDocId(target.id);
    setHighlightLine(line);
  }, [data]);

  // Auto-select the first document when the case loads so the viewer pane is
  // never empty for a freshly-seeded demo case.
  useEffect(() => {
    if (!activeDocId && data && data.documents.length > 0) {
      setActiveDocId(data.documents[0]!.id);
    }
  }, [data?.documents.length, activeDocId, data]);

  // Auto-create a conversation if none exists yet so the chat panel + prompt
  // suggestions are immediately usable.
  useEffect(() => {
    if (data && convs.length === 0) {
      void startConversation(caseId, "Case discussion").then(() => {
        qc.invalidateQueries({ queryKey: caseKeys.conversations(caseId) });
      });
    }
  }, [data?.case.id, convs.length, caseId, qc]);

  // The promote form fires a window event after a successful promote so we
  // can jump straight to the editor with the new draft.
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as { reportId: string };
      setDrawer({ kind: "report", reportId: detail.reportId });
    };
    window.addEventListener("open-report", handler);
    return () => window.removeEventListener("open-report", handler);
  }, []);

  if (isLoading) return <div className="p-6 text-slate-500">Loading case…</div>;
  if (error) return <div className="p-6 text-red-700">{(error as Error).message}</div>;
  if (!data) return <div className="p-6 text-slate-500">Case not found.</div>;

  const { case: c, documents, media } = data;
  const activeDoc = documents.find((d) => d.id === activeDocId) ?? null;

  return (
    <div className="flex flex-col h-[calc(100vh-var(--shell-topbar-height,56px))]">
      {/* Case header */}
      <div className="border-b border-slate-200 bg-white px-6 py-3 flex-shrink-0">
        <div className="text-xs text-slate-500 font-mono">{c.case_number}</div>
        <h1 className="text-xl font-semibold leading-tight">{c.title}</h1>
        <div className="flex gap-2 mt-1 items-center text-xs text-slate-600">
          <span className="px-2 py-0.5 rounded bg-slate-100 capitalize">
            {c.classification.replace("_", " ")}
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-100">{c.status}</span>
          <span className="px-2 py-0.5 rounded bg-slate-100">retention: {c.retention_policy}</span>
          <span className="px-2 py-0.5 rounded bg-slate-100">{documents.length} docs · {media.length} media · {reports.length} reports</span>
        </div>
        {c.description ? (
          <p className="text-sm text-slate-600 mt-2 max-w-4xl">{c.description}</p>
        ) : null}
      </div>

      {/* Three panes */}
      <div className="flex-1 grid grid-cols-12 overflow-hidden">
        {/* Left: documents + media + reports */}
        <aside className="col-span-3 border-r border-slate-200 bg-slate-50 overflow-y-auto">
          <SidebarSection title="Documents" count={documents.length}>
            <RegisterDocumentInline caseId={caseId} onDone={() => qc.invalidateQueries({ queryKey: caseKeys.detail(caseId) })} />
            <ul className="space-y-1 mt-2">
              {documents.map((d) => (
                <li key={d.id}>
                  <button
                    type="button"
                    onClick={() => setActiveDocId(d.id === activeDocId ? null : d.id)}
                    className={`w-full text-left text-xs px-2 py-1 rounded ${
                      activeDocId === d.id ? "bg-blue-100 text-blue-900" : "hover:bg-slate-100"
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>📄</span>
                      <span className="font-medium truncate">{d.original_filename}</span>
                    </div>
                    <div className="flex items-center justify-between mt-0.5">
                      <span className="font-mono text-[10px] text-slate-500">{d.sha256.slice(0, 12)}…</span>
                      <ExtractionBadge caseId={caseId} documentId={d.id} />
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </SidebarSection>

          <SidebarSection title="Media" count={media.length}>
            <RegisterMediaInline caseId={caseId} onDone={() => qc.invalidateQueries({ queryKey: caseKeys.detail(caseId) })} />
            <ul className="space-y-1 mt-2">
              {media.map((m: MediaInput) => (
                <li key={m.id} className="text-xs px-2 py-1 rounded hover:bg-slate-100">
                  🎥 <span className="font-medium">{m.source_type}</span>
                  <div className="text-[10px] text-slate-500">{m.duration_seconds}s</div>
                </li>
              ))}
            </ul>
          </SidebarSection>

          <SidebarSection title="Reports" count={reports.length}>
            <ul className="space-y-1 mt-2">
              {reports.map((r: Report) => (
                <li key={r.id}>
                  <button
                    type="button"
                    onClick={() => setDrawer({ kind: "report", reportId: r.id })}
                    className="w-full text-left text-xs px-2 py-1 rounded hover:bg-slate-100"
                  >
                    📋 <span className="font-medium">{r.title}</span>
                    <div className="text-[10px] text-slate-500">{r.status}</div>
                  </button>
                </li>
              ))}
              {reports.length === 0 ? (
                <li className="text-xs text-slate-500 px-2">
                  Promote an AI answer to create one.
                </li>
              ) : null}
            </ul>
          </SidebarSection>
        </aside>

        {/* Center: document viewer placeholder */}
        <section className="col-span-5 border-r border-slate-200 bg-white overflow-y-auto">
          {activeDoc ? (
            <DocumentViewer caseId={caseId} doc={activeDoc} highlightLine={highlightLine} />
          ) : (
            <DocumentEmpty />
          )}
        </section>

        {/* Right: chat */}
        <section className="col-span-4 bg-white overflow-hidden">
          <ChatPanel
            caseId={caseId}
            documents={documents}
            media={media}
            onPromote={(m) => setDrawer({ kind: "promote", sourceMessage: m })}
            onCitationClick={handleCitationClick}
          />
        </section>
      </div>

      <ReportDrawer
        caseId={caseId}
        state={drawer}
        onClose={() => setDrawer({ kind: "closed" })}
        onCitationClick={handleCitationClick}
      />
    </div>
  );
}

function SidebarSection({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-slate-200 p-3">
      <div className="text-xs uppercase tracking-wide text-slate-500 mb-2 flex justify-between">
        <span>{title}</span>
        <span>{count}</span>
      </div>
      {children}
    </div>
  );
}

function ExtractionBadge({ caseId, documentId }: { caseId: string; documentId: string }) {
  const { data } = useQuery({
    queryKey: ["doc-text-status", caseId, documentId],
    queryFn: () => getDocumentTextStatus(caseId, documentId),
    staleTime: 60_000,
  });
  if (!data) {
    return <span className="text-[10px] text-slate-400">…</span>;
  }
  const { method, non_ws_chars } = data;
  const palette: Record<DocumentTextStatus["method"], string> = {
    "text-layer": "bg-emerald-100 text-emerald-800",
    "ocr":        "bg-amber-100 text-amber-800",
    "plaintext":  "bg-slate-100 text-slate-700",
    "empty":      "bg-red-100 text-red-800",
    "error":      "bg-red-100 text-red-800",
  };
  const label: Record<DocumentTextStatus["method"], string> = {
    "text-layer": "text",
    "ocr":        "ocr",
    "plaintext":  "text",
    "empty":      "empty",
    "error":      "err",
  };
  return (
    <span
      className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${palette[method]}`}
      title={`Extraction: ${method} · ${non_ws_chars.toLocaleString()} non-ws chars · the AI can ${method === "empty" || method === "error" ? "NOT" : ""} see this doc`}
    >
      {label[method]} · {non_ws_chars >= 1000 ? `${Math.round(non_ws_chars / 1000)}k` : non_ws_chars}
    </span>
  );
}

function DocumentEmpty() {
  return (
    <div className="h-full flex items-center justify-center text-slate-400 text-sm text-center p-6">
      Select a document on the left to view it,<br />
      or chat with the case on the right.
    </div>
  );
}

function DocumentViewer({
  caseId,
  doc,
  highlightLine,
}: {
  caseId: string;
  doc: Document;
  highlightLine: number | null;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["doc-text", caseId, doc.id],
    queryFn: () => getDocumentText(caseId, doc.id),
  });
  const lineRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const [flashLine, setFlashLine] = useState<number | null>(null);

  useEffect(() => {
    if (!highlightLine || !data) return;
    const el = lineRefs.current[highlightLine];
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlashLine(highlightLine);
    const timeout = window.setTimeout(() => setFlashLine(null), 2400);
    return () => window.clearTimeout(timeout);
  }, [highlightLine, data]);

  const lines = data?.lines ?? [];

  return (
    <div className="p-6 h-full flex flex-col">
      <h2 className="font-semibold text-base">{doc.original_filename}</h2>
      <div className="text-[11px] text-slate-500 mt-1 space-y-0.5 flex-shrink-0">
        <div><strong>URI:</strong> <code className="text-slate-700">{doc.storage_uri}</code></div>
        <div className="font-mono"><strong>sha256:</strong> {doc.sha256.slice(0, 24)}…</div>
        <div>
          <strong>{doc.mime_type}</strong> · {doc.size_bytes} bytes · {doc.page_count} page(s) ·
          <span className="ml-1">{data?.line_count ?? 0} lines</span>
        </div>
      </div>
      <div className="mt-3 flex-1 min-h-0 border border-slate-200 rounded bg-slate-50 overflow-auto">
        {isLoading ? (
          <div className="p-4 text-sm text-slate-500">Extracting text…</div>
        ) : error ? (
          <div className="p-4 text-sm text-red-700">{(error as Error).message}</div>
        ) : lines.length === 0 ? (
          <div className="p-4 text-sm text-slate-500">(no extractable text)</div>
        ) : (
          <div className="font-mono text-[12.5px] leading-relaxed">
            {lines.map((line, i) => {
              const n = i + 1;
              const isFlash = flashLine === n;
              return (
                <div
                  key={n}
                  ref={(el) => { lineRefs.current[n] = el; }}
                  className={
                    `flex gap-3 px-3 py-0.5 transition-colors duration-700 ` +
                    (isFlash ? "bg-yellow-200" : "hover:bg-slate-100")
                  }
                >
                  <span className="text-slate-400 select-none w-10 text-right shrink-0">{n}</span>
                  <span className="whitespace-pre-wrap break-words">{line || " "}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function RegisterDocumentInline({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [uri, setUri] = useState("");
  const [name, setName] = useState("");
  const m = useMutation({
    mutationFn: () => registerDocument(caseId, { storage_uri: uri, original_filename: name || uri }),
    onSuccess: () => { setUri(""); setName(""); setOpen(false); onDone(); },
  });
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs text-blue-700 hover:underline"
      >
        + Register document
      </button>
    );
  }
  return (
    <div className="space-y-1.5">
      <input className="w-full border border-slate-300 rounded px-2 py-1 text-xs" placeholder="filename.pdf (under uploads/)" value={uri} onChange={(e) => setUri(e.target.value)} />
      <input className="w-full border border-slate-300 rounded px-2 py-1 text-xs" placeholder="Original filename" value={name} onChange={(e) => setName(e.target.value)} />
      {m.error ? <div className="text-[11px] text-red-700">{(m.error as Error).message}</div> : null}
      <div className="flex gap-1">
        <button type="button" onClick={() => m.mutate()} disabled={m.isPending || !uri.trim()} className="text-xs px-2 py-0.5 rounded bg-blue-600 text-white disabled:opacity-50">
          {m.isPending ? "…" : "Add"}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="text-xs px-2 py-0.5 rounded border border-slate-300">
          Cancel
        </button>
      </div>
    </div>
  );
}

function RegisterMediaInline({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [uri, setUri] = useState("");
  const [sourceType, setSourceType] = useState<MediaInput["source_type"]>("bodycam");
  const m = useMutation({
    mutationFn: () => registerMedia(caseId, {
      storage_uri: uri,
      source_type: sourceType,
      sha256: "0".repeat(64),
    }),
    onSuccess: () => { setUri(""); setOpen(false); onDone(); },
  });
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs text-blue-700 hover:underline"
      >
        + Register media (§13663(c)(2))
      </button>
    );
  }
  return (
    <div className="space-y-1.5">
      <input className="w-full border border-slate-300 rounded px-2 py-1 text-xs" placeholder="storage URI" value={uri} onChange={(e) => setUri(e.target.value)} />
      <select className="w-full border border-slate-300 rounded px-2 py-1 text-xs" value={sourceType} onChange={(e) => setSourceType(e.target.value as MediaInput["source_type"])}>
        {(["bodycam", "dashcam", "interview_audio", "interview_video", "call_recording", "other"] as const).map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
      {m.error ? <div className="text-[11px] text-red-700">{(m.error as Error).message}</div> : null}
      <div className="flex gap-1">
        <button type="button" onClick={() => m.mutate()} disabled={m.isPending || !uri.trim()} className="text-xs px-2 py-0.5 rounded bg-blue-600 text-white disabled:opacity-50">
          {m.isPending ? "…" : "Add"}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="text-xs px-2 py-0.5 rounded border border-slate-300">
          Cancel
        </button>
      </div>
    </div>
  );
}
