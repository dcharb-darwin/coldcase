// Parses citation tokens out of AI-generated text and renders them as
// clickable chips. Two formats are supported during the inline-text →
// multimodal transition (both declared server-side in
// routers/conversations.py):
//
//   1. Line-anchored (text-extracted docs):
//      [src: <filename>, L<n>]
//   2. Page+quote (gpt-5.x multimodal — sees the PDF natively):
//      [src: <filename>, p<page>, "<verbatim quote>"]

import { useMemo } from "react";

export interface Citation {
  filename: string;
  /** "line" mode: a 1-indexed line into the server's text extraction.
   *  "page" mode: a 1-indexed PDF page number paired with `quote`. */
  mode: "line" | "page";
  line?: number;
  page?: number;
  quote?: string;
  raw: string;
}

// Page+quote form must be tried first because its regex would otherwise be
// mistakenly captured by the line form's looser comma split.
const CITATION_REGEX_PAGE = /\[src:\s*([^,\]]+?)\s*,\s*p\s*(\d+)\s*,\s*"([^"]+)"\s*\]/gi;
const CITATION_REGEX_LINE = /\[src:\s*([^,\]]+?)\s*,\s*L\s*(\d+)\s*\]/gi;
const CITATION_REGEX_COMBINED = new RegExp(
  `${CITATION_REGEX_PAGE.source}|${CITATION_REGEX_LINE.source}`,
  "gi",
);

function parseMatch(m: RegExpMatchArray): Citation {
  // Page+quote: groups 1,2,3 — filename, page, quote
  if (m[1] !== undefined && m[2] !== undefined && m[3] !== undefined) {
    return {
      filename: m[1].trim(),
      mode: "page",
      page: Number(m[2]),
      quote: m[3],
      raw: m[0],
    };
  }
  // Line form: groups 4,5 — filename, line
  return {
    filename: m[4]!.trim(),
    mode: "line",
    line: Number(m[5]!),
    raw: m[0],
  };
}

export function extractCitations(text: string): Citation[] {
  const out: Citation[] = [];
  for (const m of text.matchAll(CITATION_REGEX_COMBINED)) {
    out.push(parseMatch(m));
  }
  return out;
}

interface CitationTextProps {
  text: string;
  onCitationClick: (filename: string, line: number) => void;
  /** Filenames the parent knows about — unknown filenames render dimmed to flag the mismatch. */
  knownFilenames?: string[];
  className?: string;
}

interface RenderedPart {
  type: "text" | "citation";
  value: string;
  citation?: Citation;
}

function splitText(text: string): RenderedPart[] {
  const parts: RenderedPart[] = [];
  let lastIndex = 0;
  for (const match of text.matchAll(CITATION_REGEX_COMBINED)) {
    const start = match.index ?? 0;
    if (start > lastIndex) parts.push({ type: "text", value: text.slice(lastIndex, start) });
    parts.push({ type: "citation", value: match[0]!, citation: parseMatch(match) });
    lastIndex = start + match[0]!.length;
  }
  if (lastIndex < text.length) parts.push({ type: "text", value: text.slice(lastIndex) });
  return parts;
}

export default function CitationText({ text, onCitationClick, knownFilenames, className }: CitationTextProps) {
  const parts = useMemo(() => splitText(text), [text]);
  return (
    <span className={`whitespace-pre-wrap leading-relaxed ${className ?? ""}`}>
      {parts.map((p, i) => {
        if (p.type === "text") return p.value;
        const c = p.citation!;
        const known = !knownFilenames || knownFilenames.includes(c.filename);
        const anchor =
          c.mode === "page"
            ? `p${c.page} · "${(c.quote ?? "").slice(0, 28)}${(c.quote ?? "").length > 28 ? "…" : ""}"`
            : `L${c.line}`;
        const tooltip =
          c.mode === "page"
            ? `Open ${c.filename} at page ${c.page} — quote: "${c.quote}"`
            : `Open ${c.filename} at line ${c.line}`;
        // Phase A: clicking still calls onCitationClick(filename, line).
        // For page-mode, until Phase B lands the PDF viewer with quote
        // highlight, we pass the page number in place of line — the
        // DocumentViewer in line-extraction mode will simply switch to
        // the document; explicit page+quote highlight comes in Phase B.
        const numeric = c.mode === "page" ? (c.page ?? 1) : (c.line ?? 1);
        return (
          <button
            key={i}
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onCitationClick(c.filename, numeric);
            }}
            title={tooltip}
            className={
              `inline-flex items-center align-baseline mx-0.5 px-1.5 py-0.5 rounded-md text-[10px] font-mono border ` +
              (known
                ? `border-blue-300 bg-blue-50 text-blue-800 hover:bg-blue-100 hover:border-blue-500`
                : `border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100`)
            }
          >
            📎 {c.filename.length > 32 ? `${c.filename.slice(0, 28)}…` : c.filename} · {anchor}
          </button>
        );
      })}
    </span>
  );
}
