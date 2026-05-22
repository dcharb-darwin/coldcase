"""Plausibility scoring for "is this the same person across cases?"

The graph layer emits SAME_NAME_AS edges between Person rows on
different cases that share a normalized name. That's the loosest
possible match — and on its own it's prone to flagging coincidence.
A "Mike Halberd" on a 1992 case in Indiana is almost certainly NOT
the same "Mike Halberd" who shows up on a 1945 case in South
Carolina, even though the names normalize identically.

This module composes confidence from three independent signals:

  1. Temporal proximity  — the cases' incident dates. A 47-year gap
     between case events makes "same officer" or "same witness"
     biologically implausible.

  2. Agency / jurisdiction match — `agency_ori_snapshot` on the case.
     Same ORI suggests the same investigator pool; different ORIs
     suggest different agencies in different jurisdictions.

  3. Name distinctiveness — full names with middle tokens are rarer
     than common first-name-only entries. A heuristic, but useful:
     "James M. Hinton" is more uniquely identifying than "John Smith".

Each signal returns a multiplier in [0, 1]; the combined confidence
is their product applied to a base value. Reasons attached to the
edge tell the UI WHY confidence is what it is, so the detective sees
"cases 47 years apart" not just a low number.

We DO NOT suppress matches entirely — the detective might be working
a cold case that spans decades and genuinely involves the same person.
Confidence + reasons let the UI calibrate uncertainty visibly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


# ── Common-name corpus (frequency heuristic — small, deliberately limited) ──
# Hard-coded short list of names so common they should reduce confidence.
# Not a serious frequency model — just the most common-by-far US names so
# obvious false positives get caught. Extend or replace with a per-tenant
# corpus when we have one.


_COMMON_FIRST_NAMES = {
    "james", "robert", "john", "michael", "william", "david", "richard",
    "joseph", "thomas", "charles", "mary", "patricia", "jennifer", "linda",
    "elizabeth", "barbara", "susan", "jessica", "sarah", "karen",
}
_COMMON_SURNAMES = {
    "smith", "johnson", "williams", "brown", "jones", "garcia", "miller",
    "davis", "rodriguez", "martinez", "hernandez", "lopez", "gonzalez",
    "wilson", "anderson", "thomas", "taylor", "moore", "jackson", "martin",
}


# ── Score ranges ─────────────────────────────────────────────────────────────
# Each signal multiplier. Keep these readable — the magic numbers belong in
# one place so attorneys can tune them.


def _temporal_score(a: Optional[date], b: Optional[date]) -> tuple[float, Optional[str]]:
    """Lower confidence as the gap between case incident dates grows."""
    if a is None or b is None:
        return 0.85, None  # unknown gap — slight haircut, no explanation needed
    years_apart = abs((a - b).days) / 365.25
    if years_apart <= 5:
        return 1.0, None
    if years_apart <= 15:
        return 0.9, None
    if years_apart <= 30:
        return 0.65, f"cases {round(years_apart)} years apart"
    if years_apart <= 50:
        return 0.25, f"cases {round(years_apart)} years apart — biologically improbable"
    return 0.05, f"cases {round(years_apart)} years apart — almost certainly different people"


def _agency_score(a_ori: str, b_ori: str) -> tuple[float, Optional[str]]:
    a = (a_ori or "").strip()
    b = (b_ori or "").strip()
    if not a or not b:
        return 0.85, None  # one or both unknown — slight haircut
    if a == b:
        return 1.0, None
    # Different ORI prefixes generally mean different states (first 2
    # chars of ORI = state abbreviation). Penalize cross-state more.
    if a[:2].upper() != b[:2].upper():
        return 0.3, f"different agency / state ({a} vs {b})"
    return 0.6, f"different agency within state ({a} vs {b})"


def _distinctiveness_score(name: str) -> tuple[float, Optional[str]]:
    """Heuristic: full names with multiple tokens (including a middle
    name or initial) are more uniquely identifying than common single
    first names. We don't have a real frequency corpus; the common-name
    list catches the obvious false positives."""
    tokens = [t for t in (name or "").lower().split() if t and t.isalnum()]
    if not tokens:
        return 0.5, None
    # Strip 1-2 char initial tokens for the rarity check; they're
    # signal-bearing for distinctiveness but not for "is this a common name".
    full_tokens = [t for t in tokens if len(t) >= 3]
    if not full_tokens:
        return 0.5, None
    # Heuristic 1: token count after the initial filter.
    if len(tokens) == 1:
        # Single-token name ("Hinton" / "Smith"). Common-surname penalty.
        if tokens[0] in _COMMON_SURNAMES:
            return 0.4, f"very common single-name match ({tokens[0]})"
        return 0.7, None
    # Heuristic 2: first + surname both on the common list.
    first = full_tokens[0]
    last = full_tokens[-1]
    common = first in _COMMON_FIRST_NAMES and last in _COMMON_SURNAMES
    if common:
        return 0.55, f"common first+surname combination ({first} {last})"
    if first in _COMMON_FIRST_NAMES or last in _COMMON_SURNAMES:
        return 0.85, None
    # Three+ tokens (e.g. "James M. Hinton") → distinctive.
    if len(tokens) >= 3:
        return 1.0, None
    return 0.95, None


# ── Combined score ───────────────────────────────────────────────────────────


@dataclass
class PlausibilityResult:
    """The combined confidence in `score` and the reasons it isn't 1.0.

    `reasons` is human-readable, intended for UI display next to the
    edge / conflict hit. Order is most-impactful first."""
    score: float
    reasons: list[str]


def same_person_plausibility(
    *,
    name: str,
    case_a_date: Optional[date | datetime],
    case_b_date: Optional[date | datetime],
    case_a_ori: str,
    case_b_ori: str,
) -> PlausibilityResult:
    """Final confidence in [0, 1] for "these two Person records refer to
    the same individual" — independent of role. Multiply this into the
    base SAME_NAME_AS edge confidence.

    Cases without dates / ORIs aren't penalized hard — we don't want to
    drown active cases with missing metadata. They take a small haircut.
    """
    def _as_date(v: Optional[date | datetime]) -> Optional[date]:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.date()
        return v

    t_score, t_reason = _temporal_score(_as_date(case_a_date), _as_date(case_b_date))
    g_score, g_reason = _agency_score(case_a_ori, case_b_ori)
    d_score, d_reason = _distinctiveness_score(name)

    # Multiplicative — any one strong signal can drop confidence; all
    # signals weak does not magically rescue it.
    combined = t_score * g_score * d_score
    reasons = [r for r in (t_reason, g_reason, d_reason) if r]
    return PlausibilityResult(score=round(combined, 3), reasons=reasons)
