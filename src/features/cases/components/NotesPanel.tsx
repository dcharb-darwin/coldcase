import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createNote, deleteNote, listNotes, updateNote,
  type Note, type NoteSubjectKind,
} from "@/lib/api/coldcase";

/**
 * Freeform detective notes. Sibling to tags (closed vocab) and timeline
 * entries (dated events) — this is for working memory: "call CBI Tuesday",
 * "DA wants §187 brief by Friday". Supports threaded replies so a follow-up
 * call lives under the original clue, not as a fresh top-level scratch.
 *
 * Scope-agnostic: pass `subjectKind` + `subjectId` to scope to a case,
 * document, or report. The same component drives all three surfaces.
 */
export default function NotesPanel({
  caseId, subjectKind = "case", subjectId, compact = false,
}: {
  caseId: string;
  subjectKind?: NoteSubjectKind;
  subjectId?: string;
  /** Smaller header + tighter padding when embedded next to other content. */
  compact?: boolean;
}) {
  const sid = subjectId ?? caseId;
  const qc = useQueryClient();
  const queryKey = ["case-notes", caseId, subjectKind, sid];

  const { data: notes = [], isLoading } = useQuery({
    queryKey,
    queryFn: () => listNotes(caseId, { subjectKind, subjectId: sid }),
  });

  const [draft, setDraft] = useState("");
  const invalidate = () => qc.invalidateQueries({ queryKey });

  const createMut = useMutation({
    mutationFn: (vars: { body: string; parent_note_id?: string }) => createNote(caseId, {
      subject_kind: subjectKind, subject_id: sid,
      body: vars.body.trim(),
      parent_note_id: vars.parent_note_id,
    }),
    onSuccess: () => { setDraft(""); invalidate(); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteNote(caseId, id),
    onSuccess: invalidate,
  });

  // Build the tree. Orphans (parent points to a deleted note) become
  // top-level — defensive against deletion of a parent.
  const tree = useMemo(() => {
    const byId = new Map<string, Note>(notes.map((n) => [n.id, n]));
    const childrenOf = new Map<string, Note[]>();
    const roots: Note[] = [];
    for (const n of notes) {
      const parentId = n.parent_note_id || "";
      if (parentId && byId.has(parentId)) {
        const arr = childrenOf.get(parentId) ?? [];
        arr.push(n);
        childrenOf.set(parentId, arr);
      } else {
        roots.push(n);
      }
    }
    // Children oldest-first inside a thread, roots newest-first so fresh
    // discussion floats up.
    for (const arr of childrenOf.values()) {
      arr.sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""));
    }
    roots.sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""));
    return { roots, childrenOf };
  }, [notes]);

  return (
    <section>
      <div className="flex items-baseline justify-between mb-2">
        <h3 className={compact
          ? "text-[12px] font-semibold text-slate-900"
          : "text-[15px] font-semibold text-slate-900"}
        >
          Notes
        </h3>
        <span className="text-[11px] text-slate-500">
          {notes.length} note{notes.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="mb-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Working scratch: questions to chase, calls to make, hypotheses to test. Not part of the §13663 chain."
          rows={2}
          className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
        <div className="flex items-center justify-end gap-2 mt-1">
          {createMut.error ? (
            <div className="flex-1 text-xs text-red-700">{(createMut.error as Error).message}</div>
          ) : null}
          <button
            type="button"
            disabled={createMut.isPending || !draft.trim()}
            onClick={() => createMut.mutate({ body: draft })}
            className="px-3 py-1 text-xs rounded bg-blue-600 text-white disabled:opacity-50"
          >
            {createMut.isPending && !createMut.variables?.parent_note_id ? "Saving…" : "Add note"}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-xs text-slate-500">Loading notes…</div>
      ) : notes.length === 0 ? (
        <div className="text-xs text-slate-400 italic">
          No notes yet. Notes are private scratch — they don't appear in the audit chain
          or in any export.
        </div>
      ) : (
        <ul className="space-y-1.5">
          {tree.roots.map((n) => (
            <NoteTreeRow
              key={n.id}
              note={n}
              depth={0}
              childrenOf={tree.childrenOf}
              onUpdate={(id, body) => updateNote(caseId, id, body).then(invalidate)}
              onDelete={(id) => deleteMut.mutate(id)}
              onReply={(parentId, body) => createMut.mutate({ body, parent_note_id: parentId })}
              isReplying={(parentId) =>
                createMut.isPending && createMut.variables?.parent_note_id === parentId
              }
            />
          ))}
        </ul>
      )}
    </section>
  );
}


function NoteTreeRow({
  note, depth, childrenOf, onUpdate, onDelete, onReply, isReplying,
}: {
  note: Note;
  depth: number;
  childrenOf: Map<string, Note[]>;
  onUpdate: (id: string, body: string) => void;
  onDelete: (id: string) => void;
  onReply: (parentId: string, body: string) => void;
  isReplying: (parentId: string) => boolean;
}) {
  const kids = childrenOf.get(note.id) ?? [];

  return (
    <li>
      <NoteRow
        note={note}
        depth={depth}
        onUpdate={(body) => onUpdate(note.id, body)}
        onDelete={() => onDelete(note.id)}
        onReply={(body) => onReply(note.id, body)}
        replyPending={isReplying(note.id)}
      />
      {kids.length > 0 ? (
        <ul className="mt-1.5 space-y-1.5 border-l-2 border-slate-200 pl-3">
          {kids.map((k) => (
            <NoteTreeRow
              key={k.id}
              note={k}
              depth={depth + 1}
              childrenOf={childrenOf}
              onUpdate={onUpdate}
              onDelete={onDelete}
              onReply={onReply}
              isReplying={isReplying}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}


function NoteRow({
  note, depth, onUpdate, onDelete, onReply, replyPending,
}: {
  note: Note;
  depth: number;
  onUpdate: (body: string) => void;
  onDelete: () => void;
  onReply: (body: string) => void;
  replyPending: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [replying, setReplying] = useState(false);
  const [draft, setDraft] = useState(note.body);
  const [replyDraft, setReplyDraft] = useState("");
  const updated = note.updated_at ? new Date(note.updated_at) : null;
  const justNow = updated && (Date.now() - updated.getTime()) < 60_000;
  return (
    <div className={"border border-slate-200 rounded p-2 bg-white group " + (depth > 0 ? "bg-slate-50/40" : "")}>
      {editing ? (
        <>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={Math.min(8, Math.max(2, draft.split("\n").length))}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
            autoFocus
          />
          <div className="flex justify-end gap-2 mt-1">
            <button
              type="button"
              onClick={() => { setEditing(false); setDraft(note.body); }}
              className="px-2 py-0.5 text-[11px] rounded border border-slate-300 hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!draft.trim() || draft.trim() === note.body}
              onClick={() => { onUpdate(draft.trim()); setEditing(false); }}
              className="px-2 py-0.5 text-[11px] rounded bg-blue-600 text-white disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </>
      ) : (
        <div className="flex items-start gap-2">
          <div className="flex-1 min-w-0">
            <div className="text-sm text-slate-900 whitespace-pre-wrap leading-relaxed break-words">
              {note.body}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              {justNow ? "just now" : updated?.toLocaleString()} · {note.updated_by || note.created_by}
            </div>
          </div>
          <div className="opacity-0 group-hover:opacity-100 flex gap-1 shrink-0 transition-opacity">
            <button
              type="button"
              onClick={() => setReplying((v) => !v)}
              className="px-1.5 py-0.5 text-[11px] text-slate-500 hover:text-blue-700"
            >
              reply
            </button>
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="px-1.5 py-0.5 text-[11px] text-slate-500 hover:text-slate-900"
            >
              edit
            </button>
            <button
              type="button"
              onClick={onDelete}
              className="px-1.5 py-0.5 text-[11px] text-slate-400 hover:text-red-700"
            >
              remove
            </button>
          </div>
        </div>
      )}

      {replying ? (
        <div className="mt-2 pt-2 border-t border-slate-100">
          <textarea
            value={replyDraft}
            onChange={(e) => setReplyDraft(e.target.value)}
            placeholder="Reply — follow-up call, contradicting evidence, next step…"
            rows={2}
            className="w-full border border-slate-300 rounded px-2 py-1 text-xs bg-white"
            autoFocus
          />
          <div className="flex justify-end gap-2 mt-1">
            <button
              type="button"
              onClick={() => { setReplying(false); setReplyDraft(""); }}
              className="px-2 py-0.5 text-[11px] rounded border border-slate-300 hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!replyDraft.trim() || replyPending}
              onClick={() => {
                onReply(replyDraft.trim());
                setReplying(false);
                setReplyDraft("");
              }}
              className="px-2 py-0.5 text-[11px] rounded bg-blue-600 text-white disabled:opacity-50"
            >
              {replyPending ? "Saving…" : "Reply"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
