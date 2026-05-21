"""Closed-vocabulary cognitive bias flags for the red-team agent.

Why closed: a free-text vocabulary lets the LLM invent flags that flatter
the detective ("rigorous_thinking", "appropriate_skepticism"). A closed
list with attorney-reviewed wording can be filtered, audited, and
explained in court.

Each entry has:
- slug: the value the LLM must return (anything else is dropped at parse)
- label: UI display string
- tooltip: one-sentence explanation shown on hover, written for a
  non-specialist reader (city attorney, jury)

Vocab is hard-coded for now; per-tenant override is a future enhancement
gated on a real tenant ask (see hypothesis-agents.md, open question #1).
"""

from __future__ import annotations

from typing import TypedDict


class BiasFlag(TypedDict):
    slug: str
    label: str
    tooltip: str


BIAS_FLAGS: list[BiasFlag] = [
    {
        "slug": "confirmation_bias",
        "label": "Confirmation bias",
        "tooltip": "Evidence selected to support the conclusion rather than test it.",
    },
    {
        "slug": "anchoring",
        "label": "Anchoring",
        "tooltip": "Conclusion anchored on the first witness statement or first hypothesis raised.",
    },
    {
        "slug": "narrative_fallacy",
        "label": "Narrative fallacy",
        "tooltip": "Story is coherent but doesn't fit all the evidence.",
    },
    {
        "slug": "availability_bias",
        "label": "Availability bias",
        "tooltip": "Weights vivid or recent evidence more than reliable evidence.",
    },
    {
        "slug": "groupthink",
        "label": "Groupthink",
        "tooltip": "Agrees with prior investigators' framing without an independent check.",
    },
    {
        "slug": "motivated_reasoning",
        "label": "Motivated reasoning",
        "tooltip": "Conclusions appear shaped by a desired outcome.",
    },
    {
        "slug": "survivorship_bias",
        "label": "Survivorship bias",
        "tooltip": "Ignores evidence that wasn't preserved or didn't make it into the file.",
    },
    {
        "slug": "recency_bias",
        "label": "Recency bias",
        "tooltip": "Weights newer evidence more than reliable older evidence.",
    },
    {
        "slug": "attribution_error",
        "label": "Attribution error",
        "tooltip": "Infers motive or character from situation alone.",
    },
]


BIAS_SLUGS = {b["slug"] for b in BIAS_FLAGS}


def is_valid_bias_slug(slug: str) -> bool:
    return slug in BIAS_SLUGS


def bias_vocab_for_prompt() -> str:
    """Format the vocab as a system-prompt block — slug + tooltip on each line."""
    return "\n".join(f"- {b['slug']}: {b['tooltip']}" for b in BIAS_FLAGS)
