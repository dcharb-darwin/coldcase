"""Single source of truth for citation-token parsing.

Matches both formats produced by the conversations router:
  [src: <filename>, L<line>]                          — text-extracted docs (legacy)
  [src: <filename>, p<page>, "<verbatim quote>"]      — multimodal mode
"""

from __future__ import annotations

import re


CITATION_REGEX = re.compile(
    r"\[src:\s*[^,\]]+?\s*,\s*(?:L\s*\d+|p\s*\d+\s*,\s*\"[^\"]+\")\s*\]",
    re.IGNORECASE,
)


def citation_coverage(text: str) -> dict:
    """Count paragraph-level citation density.

    Paragraphs without a `[src: ...]` token are flagged as "unsourced".
    Returns a dict — same shape across F7 chain export + F15 case manifest.
    """
    paragraphs = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
    sourced = sum(1 for p in paragraphs if CITATION_REGEX.search(p))
    total = len(paragraphs)
    return {
        "paragraphs": total,
        "with_citations": sourced,
        "unsourced": total - sourced,
        "coverage_pct": round((sourced / total) * 100, 1) if total else 0.0,
    }
