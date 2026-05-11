// Parses `[src: <filename>, L<n>]` tokens out of AI-generated text and
// renders them as clickable chips. Token format mirrors the protocol
// declared server-side in routers/conversations.py::CITATION_INSTRUCTIONS.

import { useMemo } from "react";

export interface Citation {
  filename: string;
  line: number;
  raw: string;
}

const CITATION_REGEX = /\[src:\s*([^,\]]+?)\s*,\s*L\s*(\d+)\s*\]/gi;

export function extractCitations(text: string): Citation[] {
  const out: Citation[] = [];
  for (const m of text.matchAll(CITATION_REGEX)) {
    out.push({ filename: m[1]!.trim(), line: Number(m[2]!), raw: m[0]! });
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
  filename?: string;
  line?: number;
}

function splitText(text: string): RenderedPart[] {
  const parts: RenderedPart[] = [];
  let lastIndex = 0;
  for (const match of text.matchAll(CITATION_REGEX)) {
    const start = match.index ?? 0;
    if (start > lastIndex) parts.push({ type: "text", value: text.slice(lastIndex, start) });
    parts.push({
      type: "citation",
      value: match[0]!,
      filename: match[1]!.trim(),
      line: Number(match[2]!),
    });
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
        const known = !knownFilenames || knownFilenames.includes(p.filename!);
        return (
          <button
            key={i}
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onCitationClick(p.filename!, p.line!);
            }}
            title={`Open ${p.filename} at line ${p.line}`}
            className={
              `inline-flex items-center align-baseline mx-0.5 px-1.5 py-0.5 rounded-md text-[10px] font-mono border ` +
              (known
                ? `border-blue-300 bg-blue-50 text-blue-800 hover:bg-blue-100 hover:border-blue-500`
                : `border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100`)
            }
          >
            📎 {p.filename!.length > 32 ? `${p.filename!.slice(0, 28)}…` : p.filename} · L{p.line}
          </button>
        );
      })}
    </span>
  );
}
