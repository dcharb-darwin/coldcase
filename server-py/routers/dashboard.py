"""Cross-case insights for the dashboard.

Aggregates the derived graph signals (already exposed per-case under
/cases/{id}/similar and /persons/network) up to the detective's whole
caseload, so the dashboard surfaces "things to follow up on" without
requiring the detective to click into each case.

Two surfaces:
- recurring_persons: people who appear (by loose name match) on >=2 of
  the caller's cases. The detective probably already knows, but the list
  is a useful daily orientation.
- similar_case_pairs: Jaccard-similar pairs where at least one side is
  one of the caller's cases. The "other" side may or may not be theirs.
"""

from __future__ import annotations

import re as _re
from collections import defaultdict

from fastapi import APIRouter, Depends

from models import (
    Case, Person, Tag, TagAssignment, TagSubjectKind,
)
from routers._deps import CurrentUser, current_user, require_perm
from services.vendor_scope import enforce_vendor_scope


router = APIRouter(
    prefix="/dashboard", tags=["Dashboard"],
    dependencies=[Depends(enforce_vendor_scope)],
)


_HONORIFIC_RE = _re.compile(r"\b(dr|mr|mrs|ms|mx|prof|rev|sgt|det|capt|lt|hon)\.?\s+")
_PUNCT_RE = _re.compile(r"[^\w\s]+")
_WS_RE = _re.compile(r"\s+")


def _normalize_name(s: str) -> str:
    s = s.strip().lower()
    s = _HONORIFIC_RE.sub("", s)
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s)
    return s.strip()


@router.get("/insights")
@require_perm("case.read")
def dashboard_insights(
    person_limit: int = 10,
    pair_limit: int = 10,
    user: CurrentUser = Depends(current_user),
):
    """Cross-case aggregations for the dashboard.

    Scoped to cases where the caller is primary investigator. Returns
    derived data only — nothing is persisted.
    """
    my_cases = list(Case.objects(
        tenant_id=user.tenant_id, primary_investigator_id=user.user_id,
    ).only("id", "case_number", "title", "classification"))
    my_case_ids = {str(c.id) for c in my_cases}
    case_by_id = {str(c.id): c for c in my_cases}
    if not my_cases:
        return {"recurring_persons": [], "similar_case_pairs": []}

    # ── Recurring persons ───────────────────────────────────────────────
    persons = list(Person.objects(
        tenant_id=user.tenant_id, case__in=my_cases,
    ).only("name", "role", "case", "provenance"))

    by_norm: dict[str, list[Person]] = defaultdict(list)
    for p in persons:
        key = _normalize_name(p.name or "")
        if key:
            by_norm[key].append(p)

    recurring = []
    for _norm, group in by_norm.items():
        case_ids = {str(p.case.id) for p in group if p.case}
        if len(case_ids) < 2:
            continue
        canonical = max(group, key=lambda p: len(p.name or ""))
        ai_sourced_any = any(
            (p.provenance and p.provenance.source and p.provenance.source != "manual")
            for p in group
        )
        recurring.append({
            "name": canonical.name,
            "role": canonical.role,
            "case_count": len(case_ids),
            "your_case_ids": sorted(case_ids),
            "your_case_numbers": sorted(
                case_by_id[cid].case_number for cid in case_ids if cid in case_by_id
            ),
            "ai_sourced_any": ai_sourced_any,
        })
    recurring.sort(key=lambda r: (-r["case_count"], r["name"].lower()))
    recurring = recurring[: max(1, min(person_limit, 25))]

    # ── Similar case pairs ──────────────────────────────────────────────
    user_tag_ids: set[str] = {
        str(t.id)
        for t in Tag.objects(tenant_id=user.tenant_id, kind="user").only("id")
    }
    pairs: list[dict] = []
    if user_tag_ids:
        slug_by_tag_id = {
            str(t.id): t.slug
            for t in Tag.objects(tenant_id=user.tenant_id, id__in=list(user_tag_ids)).only("slug")
        }
        label_by_slug = {
            t.slug: t.label
            for t in Tag.objects(tenant_id=user.tenant_id, kind="user").only("slug", "label")
        }

        tags_by_case: dict[str, set[str]] = defaultdict(set)
        for a in TagAssignment.objects(
            tenant_id=user.tenant_id,
            subject_kind=TagSubjectKind.CASE.value,
            tag_id__in=list(user_tag_ids),
        ).only("tag_id", "subject_id"):
            slug = slug_by_tag_id.get(a.tag_id)
            if slug:
                tags_by_case[a.subject_id].add(slug)

        # Score pairs where at least one side is mine. Dedupe symmetric
        # pairs (mine, mine) so we don't show the same pair twice.
        scored: list[tuple[float, str, str, set[str]]] = []
        seen_pairs: set[frozenset] = set()
        for my_id in my_case_ids:
            my_tags = tags_by_case.get(my_id)
            if not my_tags:
                continue
            for other_id, other_tags in tags_by_case.items():
                if other_id == my_id:
                    continue
                intersect = my_tags & other_tags
                if not intersect:
                    continue
                pair_key = frozenset({my_id, other_id})
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                union = my_tags | other_tags
                score = len(intersect) / max(len(union), 1)
                scored.append((score, my_id, other_id, intersect))

        scored.sort(key=lambda t: (-t[0], t[1], t[2]))
        top = scored[: max(1, min(pair_limit, 25))]

        # Resolve the "other" cases in one round-trip. The "mine" side is
        # already in case_by_id.
        other_ids = [oid for _s, _m, oid, _i in top if oid not in case_by_id]
        if other_ids:
            for c in Case.objects(
                tenant_id=user.tenant_id, id__in=other_ids,
            ).only("id", "case_number", "title", "classification"):
                case_by_id[str(c.id)] = c

        for score, my_id, other_id, intersect in top:
            mine = case_by_id.get(my_id)
            other = case_by_id.get(other_id)
            if not mine or not other:
                continue
            pairs.append({
                "your_case_id": my_id,
                "your_case_number": mine.case_number,
                "your_case_title": mine.title,
                "other_case_id": other_id,
                "other_case_number": other.case_number,
                "other_case_title": other.title,
                "other_case_classification": other.classification,
                "other_is_yours": other_id in my_case_ids,
                "score": round(score, 3),
                "shared_tag_slugs": sorted(intersect),
                "shared_tag_labels": [label_by_slug.get(s, s) for s in sorted(intersect)],
            })

    return {
        "recurring_persons": recurring,
        "similar_case_pairs": pairs,
    }
