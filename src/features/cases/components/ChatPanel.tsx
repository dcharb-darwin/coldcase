import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listConversations,
  startConversation,
  listMessages,
  listPromptSuggestions,
  sendMessage,
  type Conversation,
  type Document,
  type MediaInput,
  type Message,
} from "@/lib/api/coldcase";
import { caseKeys, conversationKeys } from "../queryKeys";
import CitationText from "./CitationText";

interface ChatPanelProps {
  caseId: string;
  documents: Document[];
  media: MediaInput[];
  onPromote: (message: Message) => void;
  onCitationClick: (filename: string, line: number) => void;
}

export default function ChatPanel({ caseId, documents, media, onPromote, onCitationClick }: ChatPanelProps) {
  const qc = useQueryClient();
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [selectedMediaIds, setSelectedMediaIds] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const { data: conversations = [] } = useQuery({
    queryKey: caseKeys.conversations(caseId),
    queryFn: () => listConversations(caseId),
  });

  useEffect(() => {
    if (!activeConvId && conversations.length > 0) {
      setActiveConvId(conversations[0]!.id);
    }
  }, [conversations, activeConvId]);

  const startMutation = useMutation({
    mutationFn: () => startConversation(caseId),
    onSuccess: (conv: Conversation) => {
      qc.invalidateQueries({ queryKey: caseKeys.conversations(caseId) });
      setActiveConvId(conv.id);
    },
  });

  const { data: messagesData } = useQuery({
    queryKey: activeConvId ? conversationKeys.messages(activeConvId) : ["no-conv"],
    queryFn: () => listMessages(activeConvId!),
    enabled: !!activeConvId,
  });
  const messages: Message[] = messagesData?.messages ?? [];

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages.length]);

  const sendMutation = useMutation({
    mutationFn: () => sendMessage(activeConvId!, {
      content: draft,
      in_context_document_ids: [...selectedDocIds],
      in_context_media_ids: [...selectedMediaIds],
    }),
    onSuccess: () => {
      setDraft("");
      qc.invalidateQueries({ queryKey: conversationKeys.messages(activeConvId!) });
    },
  });

  const toggle = (set: Set<string>, setter: (s: Set<string>) => void, id: string) => {
    const next = new Set(set);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setter(next);
  };

  const canSend = useMemo(
    () => !!activeConvId && draft.trim().length > 0 && !sendMutation.isPending,
    [activeConvId, draft, sendMutation.isPending],
  );

  // Prompt suggestions: render against the active doc selection if any.
  const firstSelectedDocId = useMemo(() => [...selectedDocIds][0], [selectedDocIds]);
  const { data: suggestionsData } = useQuery({
    queryKey: ["prompts", "suggestions", caseId, firstSelectedDocId ?? null],
    queryFn: () => listPromptSuggestions({
      case_id: caseId,
      document_id: firstSelectedDocId,
    }),
    enabled: !!caseId,
  });
  const suggestions = suggestionsData?.suggestions ?? [];

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-200">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs uppercase tracking-wide text-slate-500">Conversation</span>
          <select
            className="text-sm border border-slate-300 rounded px-2 py-1 max-w-[16rem] truncate"
            value={activeConvId ?? ""}
            onChange={(e) => setActiveConvId(e.target.value || null)}
          >
            <option value="">— pick —</option>
            {conversations.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title || c.id.slice(-6)}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className="text-xs px-2 py-1 rounded border border-slate-300 hover:bg-slate-50"
          onClick={() => startMutation.mutate()}
          disabled={startMutation.isPending}
        >
          + New
        </button>
      </div>

      {/* Context picker */}
      {(documents.length > 0 || media.length > 0) && (
        <div className="px-3 py-2 border-b border-slate-100 bg-slate-50 text-xs">
          <div className="text-slate-500 mb-1 flex items-center justify-between gap-2">
            <span>Context for next message (audited per §13663(c)):</span>
            {selectedDocIds.size === 0 && documents.length > 0 ? (
              <span className="text-blue-700">
                ℹ All {documents.length} case docs in context — click any chip to narrow.
              </span>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {documents.map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => toggle(selectedDocIds, setSelectedDocIds, d.id)}
                className={`px-2 py-0.5 rounded border ${
                  selectedDocIds.has(d.id)
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white border-slate-300 text-slate-700"
                }`}
                title={d.storage_uri}
              >
                📄 {d.original_filename}
              </button>
            ))}
            {media.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => toggle(selectedMediaIds, setSelectedMediaIds, m.id)}
                className={`px-2 py-0.5 rounded border ${
                  selectedMediaIds.has(m.id)
                    ? "bg-amber-600 text-white border-amber-600"
                    : "bg-white border-slate-300 text-slate-700"
                }`}
                title={m.storage_uri}
              >
                🎥 {m.source_type}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {!activeConvId ? (
          <div className="text-sm text-slate-500 text-center mt-12">
            No conversation selected. Click <strong>+ New</strong> to start.
          </div>
        ) : messages.length === 0 ? (
          <div className="text-sm text-slate-500 text-center mt-12">
            Start the conversation by asking a question.
          </div>
        ) : (
          messages.map((m) => (
            <div
              key={m.id}
              className={`rounded-lg px-3 py-2 text-sm border ${
                m.role === "user"
                  ? "bg-blue-50 border-blue-100 ml-8"
                  : "bg-slate-50 border-slate-200 mr-8"
              }`}
            >
              <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-slate-500 mb-1">
                <span>
                  {m.role}
                  {m.model ? ` · ${m.model}` : ""}
                </span>
                <span className="flex items-center gap-2">
                  {m.is_first_ai_draft ? (
                    <span className="text-amber-700 font-medium">
                      📌 §13663(b) first draft (locked)
                    </span>
                  ) : null}
                  {m.role === "assistant" && !m.is_first_ai_draft ? (
                    <button
                      type="button"
                      onClick={() => onPromote(m)}
                      className="text-blue-700 hover:underline normal-case font-medium"
                    >
                      Use as official report →
                    </button>
                  ) : null}
                </span>
              </div>
              {m.role === "assistant" ? (
                <CitationText
                  text={m.content}
                  onCitationClick={onCitationClick}
                  knownFilenames={documents.map((d) => d.original_filename)}
                />
              ) : (
                <div className="whitespace-pre-wrap leading-relaxed">{m.content}</div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Suggestion chips */}
      {activeConvId && suggestions.length > 0 ? (
        <div className="border-t border-slate-100 px-3 py-2 bg-white">
          <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-1.5">
            Suggested prompts {firstSelectedDocId ? "(for selected document)" : "(case-wide)"}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {suggestions.map((s) => (
              <button
                key={s.id}
                type="button"
                title={s.description}
                onClick={() => setDraft(s.rendered_prompt)}
                disabled={s.needs_document && !firstSelectedDocId && !documents.length}
                className="px-2 py-1 rounded-full border border-slate-300 bg-slate-50 hover:bg-slate-100 text-xs disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {/* Composer */}
      <div className="border-t border-slate-200 p-3">
        <textarea
          className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm resize-none"
          rows={3}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={activeConvId ? "Ask the AI about this case…" : "Create a conversation first"}
          disabled={!activeConvId || sendMutation.isPending}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && canSend) {
              sendMutation.mutate();
            }
          }}
        />
        {sendMutation.error ? (
          <div className="text-xs text-red-700 mt-1">{(sendMutation.error as Error).message}</div>
        ) : null}
        <div className="flex justify-between items-center mt-2">
          <span className="text-xs text-slate-500">
            ⌘/Ctrl + Enter to send · {selectedDocIds.size === 0 ? `all ${documents.length}` : selectedDocIds.size} docs, {selectedMediaIds.size} media in context
          </span>
          <button
            type="button"
            disabled={!canSend}
            onClick={() => sendMutation.mutate()}
            className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white disabled:opacity-50"
          >
            {sendMutation.isPending ? "Sending…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
