import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  assignTag, listCaseTags, listTags, unassignTag,
  type CaseTagAssignment, type Tag, type TagColor, type TagSubjectKind,
} from "@/lib/api/coldcase";
import { caseKeys } from "../queryKeys";

// Tailwind class fragments keyed by tag color. Centralized so every chip
// (hero, brief, list filter) renders identically and a future palette
// change is one-block.
const COLOR_CLASSES: Record<TagColor, { chip: string; pickerHover: string; dot: string }> = {
  slate:   { chip: "bg-slate-100 text-slate-800 border-slate-300",     pickerHover: "hover:bg-slate-100",   dot: "bg-slate-400" },
  red:     { chip: "bg-red-50 text-red-800 border-red-200",            pickerHover: "hover:bg-red-50",     dot: "bg-red-500" },
  amber:   { chip: "bg-amber-50 text-amber-800 border-amber-200",      pickerHover: "hover:bg-amber-50",   dot: "bg-amber-500" },
  emerald: { chip: "bg-emerald-50 text-emerald-800 border-emerald-200",pickerHover: "hover:bg-emerald-50", dot: "bg-emerald-500" },
  blue:    { chip: "bg-blue-50 text-blue-800 border-blue-200",         pickerHover: "hover:bg-blue-50",    dot: "bg-blue-500" },
  indigo:  { chip: "bg-indigo-50 text-indigo-800 border-indigo-200",   pickerHover: "hover:bg-indigo-50",  dot: "bg-indigo-500" },
  purple:  { chip: "bg-purple-50 text-purple-800 border-purple-200",   pickerHover: "hover:bg-purple-50",  dot: "bg-purple-500" },
  pink:    { chip: "bg-pink-50 text-pink-800 border-pink-200",         pickerHover: "hover:bg-pink-50",    dot: "bg-pink-500" },
};

export function TagChip({
  tag, removable = false, onRemove, title,
}: {
  tag: Tag;
  removable?: boolean;
  onRemove?: () => void;
  title?: string;
}) {
  const cls = COLOR_CLASSES[tag.color] || COLOR_CLASSES.slate;
  const isSystem = tag.kind === "system";
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium ${cls.chip}`}
      title={title ?? tag.description ?? tag.label}
    >
      {isSystem ? (
        // Lock glyph signals "computed by the system; not user-removable."
        <span className="opacity-60" aria-hidden>🔒</span>
      ) : (
        <span className="font-mono opacity-70">#</span>
      )}
      {tag.label}
      {removable && !isSystem ? (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onRemove?.(); }}
          className="ml-0.5 -mr-1 px-1 rounded opacity-60 hover:opacity-100 hover:bg-black/10"
          title={`Remove ${tag.label}`}
          aria-label={`Remove ${tag.label}`}
        >
          ×
        </button>
      ) : null}
    </span>
  );
}

/** Row of tag chips on a case, with an inline "+ tag" picker. */
export function CaseTagBar({
  caseId, subjectKind = "case", subjectId,
}: {
  caseId: string;
  subjectKind?: TagSubjectKind;
  subjectId?: string;
}) {
  const sId = subjectId ?? caseId;
  const qc = useQueryClient();
  const { data: assignments = [] } = useQuery({
    queryKey: caseKeys.tags(caseId),
    queryFn: () => listCaseTags(caseId),
  });
  const { data: vocab = [] } = useQuery({
    queryKey: ["tags", "vocab"],
    queryFn: listTags,
    staleTime: 5 * 60_000,
  });

  const onSubject = useMemo(
    () => assignments.filter(
      (a) => a.subject_kind === subjectKind && a.subject_id === sId,
    ),
    [assignments, subjectKind, sId],
  );
  const assignedTagIds = new Set(onSubject.map((a) => a.tag_id));
  // Only show vocabulary entries that apply to this subject kind.
  const candidates = vocab.filter((t) =>
    (t.applicable_to.length === 0 || t.applicable_to.includes(subjectKind))
    && !assignedTagIds.has(t.id),
  );

  const invalidate = () => qc.invalidateQueries({ queryKey: caseKeys.tags(caseId) });
  const assignMut = useMutation({
    mutationFn: (tagId: string) => assignTag(tagId, subjectKind, sId),
    onSuccess: invalidate,
  });
  const removeMut = useMutation({
    mutationFn: (tagId: string) => unassignTag(tagId, subjectKind, sId),
    onSuccess: invalidate,
  });

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {onSubject.length === 0 ? (
        <span className="text-[11px] text-slate-400 italic">No tags yet.</span>
      ) : null}
      {onSubject.map((a: CaseTagAssignment) => (
        <TagChip
          key={a.id}
          tag={a.tag}
          removable
          onRemove={() => removeMut.mutate(a.tag_id)}
        />
      ))}
      <TagPicker
        candidates={candidates}
        onPick={(tagId) => assignMut.mutate(tagId)}
        disabled={assignMut.isPending}
      />
    </div>
  );
}

function TagPicker({
  candidates, onPick, disabled,
}: { candidates: Tag[]; onPick: (tagId: string) => void; disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement | null>(null);
  // Portal-positioned coords. The dropdown lives at document.body so it
  // can't be clipped by any scrolling ancestor (chat panel, drawer, etc).
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);

  useLayoutEffect(() => {
    if (!open || !btnRef.current) return;
    const r = btnRef.current.getBoundingClientRect();
    // Default: drop below. If the dropdown would clip the viewport bottom,
    // flip above. 280 is the max-height of the dropdown + a little slack.
    const wouldClip = r.bottom + 280 > window.innerHeight;
    const top = wouldClip ? r.top - 4 : r.bottom + 4;
    setCoords({ top, left: r.left });
  }, [open]);

  // Close on outside click + escape — simple, portal-friendly.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      // Click on the trigger itself is handled by the button's own onClick.
      if (btnRef.current?.contains(t)) return;
      // Click on the dropdown (portal'd at body) — let it close via onPick.
      const inDropdown = (t as HTMLElement)?.closest?.("[data-tag-picker]");
      if (inDropdown) return;
      setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onEsc);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  if (candidates.length === 0 && !open) return null;

  const dropdown = open && coords ? createPortal(
    <div
      data-tag-picker
      style={{
        position: "fixed",
        top: coords.top,
        left: coords.left,
        transform: coords.top < (btnRef.current?.getBoundingClientRect().top ?? 0)
          ? "translateY(-100%)"
          : undefined,
      }}
      className="z-50 bg-white border border-slate-200 rounded shadow-lg p-1 min-w-[220px] max-h-[260px] overflow-y-auto"
    >
      {candidates.length === 0 ? (
        <div className="px-2 py-1.5 text-xs text-slate-500">All tags already applied.</div>
      ) : (
        candidates.map((t) => {
          const cls = COLOR_CLASSES[t.color] || COLOR_CLASSES.slate;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => { onPick(t.id); setOpen(false); }}
              className={`w-full flex items-center gap-2 px-2 py-1 text-left text-xs rounded ${cls.pickerHover}`}
              title={t.description}
            >
              <span className={`w-2 h-2 rounded-full shrink-0 ${cls.dot}`} />
              <span className="font-medium">{t.label}</span>
              {t.description ? (
                <span className="ml-auto text-slate-500 truncate max-w-[180px]">
                  {t.description}
                </span>
              ) : null}
            </button>
          );
        })
      )}
    </div>,
    document.body,
  ) : null;

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={disabled}
        className="inline-flex items-center px-2 py-0.5 rounded-full border border-dashed border-slate-300 text-[11px] text-slate-600 hover:bg-slate-50 disabled:opacity-50"
        title="Add a tag"
      >
        + tag
      </button>
      {dropdown}
    </>
  );
}
