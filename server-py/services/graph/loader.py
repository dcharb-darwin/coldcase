"""Mongo → graph nodes + edges. Pure read; never persists.

Each loader function returns the slice of the graph it knows about.
Composing them gives the full tenant view. Edge emitters mark every
edge with the four dimensions defined in `types.py` so downstream
filtering Just Works.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Iterable

from models import (
    Case, Document, Person, TagAssignment, TagSubjectKind,
    TimelineEntry, Tag,
)
from models.hypothesis import Hypothesis

from services.graph.types import (
    CONFIDENCE_OFFICER_ACCEPTED, CONFIDENCE_OFFICER_CONFIRMED,
    CONFIDENCE_WEAK,
    EdgeKind, EdgeProvenanceSource, EdgeStatus,
    GraphEdge, GraphNode, NodeKind, node_id,
)
from services.graph.plausibility import same_person_plausibility


_HONORIFIC_RE = re.compile(r"\b(dr|mr|mrs|ms|mx|prof|rev|sgt|det|capt|lt|hon)\.?\s+")
_PUNCT_RE = re.compile(r"[^\w\s]+")
_WS_RE = re.compile(r"\s+")


def _normalize_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = _HONORIFIC_RE.sub("", s)
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


# ── Per-domain loaders ─────────────────────────────────────────────────────


def load_cases(tenant_id: str) -> tuple[list[GraphNode], list[GraphEdge]]:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    for c in Case.objects(tenant_id=tenant_id):
        nodes.append(GraphNode(
            id=node_id(NodeKind.CASE, str(c.id)),
            kind=NodeKind.CASE,
            label=c.case_number,
            attrs={
                "case_number": c.case_number,
                "title": c.title,
                "classification": c.classification,
                "status": c.status,
                "primary_investigator_id": c.primary_investigator_id,
                # Needed by the plausibility scorer for SAME_NAME_AS edges
                # and the cross-case role-conflict query.
                "date_of_incident": (
                    c.date_of_incident.isoformat() if c.date_of_incident else None
                ),
                "agency_ori_snapshot": c.agency_ori_snapshot or "",
            },
        ))
    return nodes, edges


def load_persons(tenant_id: str) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Person nodes + APPEARS_ON_CASE edges + SAME_NAME_AS / CO_OCCURS_WITH.

    Confidence rules:
      - APPEARS_ON_CASE: officer-confirmed if provenance=manual, accepted
        if AI-derived
      - SAME_NAME_AS: WEAK base, multiplied by `same_person_plausibility`
        from the temporal gap, agency ORI match, and name distinctiveness.
        A 47-year gap between cases in different states drops confidence
        toward zero; reasons are stored on the edge so the UI can explain
        why the system is uncertain. We DO NOT suppress the edge entirely
        — a detective working a cross-decade cold case might still want
        to inspect it.
      - CO_OCCURS_WITH: officer-confirmed (structural — they're both on
        the same case file)
    """
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    persons_by_case: dict[str, list[Person]] = defaultdict(list)
    persons_by_norm_name: dict[str, list[Person]] = defaultdict(list)

    # Cache per-case metadata used by the plausibility scorer so we don't
    # touch the DB inside the inner SAME_NAME_AS loop.
    case_meta: dict[str, dict] = {}
    for c in Case.objects(tenant_id=tenant_id).only(
        "id", "date_of_incident", "agency_ori_snapshot",
    ):
        case_meta[str(c.id)] = {
            "date_of_incident": c.date_of_incident,
            "agency_ori_snapshot": c.agency_ori_snapshot or "",
        }

    for p in Person.objects(tenant_id=tenant_id):
        case_raw = str(p.case.id) if p.case else ""
        if not case_raw:
            continue
        nodes.append(GraphNode(
            id=node_id(NodeKind.PERSON, str(p.id)),
            kind=NodeKind.PERSON,
            label=p.name,
            attrs={
                "name": p.name,
                "role": p.role,
                "descriptor": p.descriptor,
                "case_id": case_raw,
                "ai_sourced": bool(
                    p.provenance and (p.provenance.source or "manual") != "manual"
                ),
            },
        ))

        is_ai = bool(p.provenance and (p.provenance.source or "manual") != "manual")
        conf = CONFIDENCE_OFFICER_ACCEPTED if is_ai else CONFIDENCE_OFFICER_CONFIRMED
        prov = (
            EdgeProvenanceSource.AI_GENERATOR if is_ai
            else EdgeProvenanceSource.HUMAN_OFFICER
        )
        edges.append(GraphEdge(
            kind=EdgeKind.APPEARS_ON_CASE,
            source=node_id(NodeKind.PERSON, str(p.id)),
            target=node_id(NodeKind.CASE, case_raw),
            confidence=conf,
            provenance=prov,
            asserted_by=p.created_by,
            asserted_at=p.created_at,
            attrs={"role": p.role, "descriptor": p.descriptor},
        ))
        persons_by_case[case_raw].append(p)
        norm = _normalize_name(p.name)
        if norm:
            persons_by_norm_name[norm].append(p)

    # CO_OCCURS_WITH: persons on the same case. Undirected, emit one
    # direction; consumers can mirror if needed.
    for case_raw, ps in persons_by_case.items():
        for i, a in enumerate(ps):
            for b in ps[i + 1:]:
                edges.append(GraphEdge(
                    kind=EdgeKind.CO_OCCURS_WITH,
                    source=node_id(NodeKind.PERSON, str(a.id)),
                    target=node_id(NodeKind.PERSON, str(b.id)),
                    confidence=CONFIDENCE_OFFICER_CONFIRMED,
                    provenance=EdgeProvenanceSource.DERIVED_STRUCTURAL,
                    attrs={"case_id": case_raw},
                ))

    # SAME_NAME_AS: persons sharing a normalized name on different cases.
    # Confidence = WEAK base × plausibility (temporal gap × agency match ×
    # name distinctiveness). Reasons attached so the UI can explain
    # uncertainty visibly.
    for norm, ps in persons_by_norm_name.items():
        if len(ps) < 2:
            continue
        for i, a in enumerate(ps):
            a_case = str(a.case.id) if a.case else ""
            for b in ps[i + 1:]:
                b_case = str(b.case.id) if b.case else ""
                if a_case == b_case:
                    continue
                a_meta = case_meta.get(a_case, {})
                b_meta = case_meta.get(b_case, {})
                pr = same_person_plausibility(
                    name=a.name,
                    case_a_date=a_meta.get("date_of_incident"),
                    case_b_date=b_meta.get("date_of_incident"),
                    case_a_ori=a_meta.get("agency_ori_snapshot", ""),
                    case_b_ori=b_meta.get("agency_ori_snapshot", ""),
                )
                # WEAK base × plausibility — at perfect plausibility (1.0)
                # this stays WEAK = 0.30, matching the prior behavior. At
                # zero plausibility it collapses to nearly 0.
                confidence = round(CONFIDENCE_WEAK * pr.score, 3)
                edges.append(GraphEdge(
                    kind=EdgeKind.SAME_NAME_AS,
                    source=node_id(NodeKind.PERSON, str(a.id)),
                    target=node_id(NodeKind.PERSON, str(b.id)),
                    confidence=confidence,
                    provenance=EdgeProvenanceSource.DERIVED_SUBSTRING,
                    attrs={
                        "normalized_name": norm,
                        "plausibility_score": pr.score,
                        "implausibility_reasons": pr.reasons,
                    },
                ))
    return nodes, edges


def load_documents(tenant_id: str) -> tuple[list[GraphNode], list[GraphEdge]]:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    for d in Document.objects(tenant_id=tenant_id).only(
        "id", "case", "original_filename", "mime_type"
    ):
        case_raw = str(d.case.id) if d.case else ""
        if not case_raw:
            continue
        nodes.append(GraphNode(
            id=node_id(NodeKind.DOCUMENT, str(d.id)),
            kind=NodeKind.DOCUMENT,
            label=d.original_filename or str(d.id),
            attrs={"mime_type": d.mime_type, "case_id": case_raw},
        ))
        edges.append(GraphEdge(
            kind=EdgeKind.BELONGS_TO_CASE,
            source=node_id(NodeKind.DOCUMENT, str(d.id)),
            target=node_id(NodeKind.CASE, case_raw),
            confidence=CONFIDENCE_OFFICER_CONFIRMED,
            provenance=EdgeProvenanceSource.DERIVED_STRUCTURAL,
        ))
    return nodes, edges


def load_hypotheses(tenant_id: str) -> tuple[list[GraphNode], list[GraphEdge]]:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    for h in Hypothesis.objects(tenant_id=tenant_id):
        case_raw = str(h.case.id) if h.case else ""
        if not case_raw:
            continue
        nodes.append(GraphNode(
            id=node_id(NodeKind.HYPOTHESIS, str(h.id)),
            kind=NodeKind.HYPOTHESIS,
            label=h.title,
            attrs={
                "status": h.status,
                "origin": h.origin,
                "red_team_count": int(h.red_team_count or 0),
                "bias_flags": list(h.bias_flags or []),
                "case_id": case_raw,
            },
        ))
        edges.append(GraphEdge(
            kind=EdgeKind.ABOUT_CASE,
            source=node_id(NodeKind.HYPOTHESIS, str(h.id)),
            target=node_id(NodeKind.CASE, case_raw),
            confidence=CONFIDENCE_OFFICER_CONFIRMED,
            provenance=EdgeProvenanceSource.DERIVED_STRUCTURAL,
        ))
        parent_raw = (h.parent_hypothesis_id or "").strip()
        if parent_raw:
            edges.append(GraphEdge(
                kind=EdgeKind.ALTERNATIVE_TO,
                source=node_id(NodeKind.HYPOTHESIS, str(h.id)),
                target=node_id(NodeKind.HYPOTHESIS, parent_raw),
                confidence=CONFIDENCE_OFFICER_ACCEPTED,
                provenance=EdgeProvenanceSource.AI_RED_TEAM,
                asserted_by=h.proposed_by_model or "",
                asserted_at=h.proposed_at,
            ))
    return nodes, edges


def load_tags_and_similar(tenant_id: str) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Tag nodes + TAGGED_WITH edges + SIMILAR_VIA_TAG between cases
    sharing user-tag slugs (Jaccard at edge level — no precomputed score)."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    tag_label_by_id: dict[str, tuple[str, str]] = {}
    for t in Tag.objects(tenant_id=tenant_id):
        nid = node_id(NodeKind.TAG, str(t.id))
        nodes.append(GraphNode(
            id=nid, kind=NodeKind.TAG, label=t.label,
            attrs={"slug": t.slug, "color": t.color, "kind": t.kind},
        ))
        tag_label_by_id[str(t.id)] = (t.slug, t.label)

    # Track user tags per case for similarity computation.
    user_tag_ids: set[str] = {
        str(t.id) for t in Tag.objects(tenant_id=tenant_id, kind="user").only("id")
    }
    case_to_user_slugs: dict[str, set[str]] = defaultdict(set)

    for a in TagAssignment.objects(tenant_id=tenant_id):
        if a.tag_id not in tag_label_by_id:
            continue
        slug, label = tag_label_by_id[a.tag_id]
        subj_kind = a.subject_kind
        # Map subject_kind → NodeKind for edge source.
        if subj_kind == TagSubjectKind.CASE.value:
            source_kind = NodeKind.CASE
        elif subj_kind == TagSubjectKind.DOCUMENT.value:
            source_kind = NodeKind.DOCUMENT
        elif subj_kind == TagSubjectKind.MESSAGE.value:
            # Messages aren't in the graph — skip silently.
            continue
        elif subj_kind == TagSubjectKind.REPORT.value:
            # Reports aren't a graph node yet — skip.
            continue
        else:
            continue
        edges.append(GraphEdge(
            kind=EdgeKind.TAGGED_WITH,
            source=node_id(source_kind, a.subject_id),
            target=node_id(NodeKind.TAG, a.tag_id),
            confidence=(
                CONFIDENCE_OFFICER_ACCEPTED if (a.provenance and (a.provenance.source or "manual") != "manual")
                else CONFIDENCE_OFFICER_CONFIRMED
            ),
            provenance=(
                EdgeProvenanceSource.AI_GENERATOR if (a.provenance and (a.provenance.source or "manual") != "manual")
                else EdgeProvenanceSource.HUMAN_OFFICER
            ),
            asserted_by=a.applied_by,
            asserted_at=a.applied_at,
        ))
        if subj_kind == TagSubjectKind.CASE.value and a.tag_id in user_tag_ids:
            case_to_user_slugs[a.subject_id].add(slug)

    # SIMILAR_VIA_TAG — Jaccard at edge confidence.
    case_ids = list(case_to_user_slugs.keys())
    for i, a_id in enumerate(case_ids):
        a_slugs = case_to_user_slugs[a_id]
        if not a_slugs:
            continue
        for b_id in case_ids[i + 1:]:
            b_slugs = case_to_user_slugs[b_id]
            if not b_slugs:
                continue
            intersect = a_slugs & b_slugs
            if not intersect:
                continue
            union = a_slugs | b_slugs
            score = len(intersect) / max(len(union), 1)
            edges.append(GraphEdge(
                kind=EdgeKind.SIMILAR_VIA_TAG,
                source=node_id(NodeKind.CASE, a_id),
                target=node_id(NodeKind.CASE, b_id),
                confidence=round(score, 3),
                provenance=EdgeProvenanceSource.DERIVED_JACCARD,
                attrs={"shared_slugs": sorted(intersect)},
            ))
    return nodes, edges


def load_timeline(tenant_id: str) -> tuple[list[GraphNode], list[GraphEdge]]:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    for t in TimelineEntry.objects(tenant_id=tenant_id):
        case_raw = str(t.case.id) if t.case else ""
        if not case_raw:
            continue
        nodes.append(GraphNode(
            id=node_id(NodeKind.TIMELINE, str(t.id)),
            kind=NodeKind.TIMELINE,
            label=t.label,
            attrs={"occurred_at": t.occurred_at, "source": t.source},
        ))
        edges.append(GraphEdge(
            kind=EdgeKind.EVENT_ON_CASE,
            source=node_id(NodeKind.TIMELINE, str(t.id)),
            target=node_id(NodeKind.CASE, case_raw),
            confidence=CONFIDENCE_OFFICER_CONFIRMED,
            provenance=EdgeProvenanceSource.DERIVED_STRUCTURAL,
        ))
    return nodes, edges


# ── Aggregate loader ──────────────────────────────────────────────────────


def load_tenant_graph(tenant_id: str) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Full tenant graph in one shot. Cached by the backend that calls this."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    for loader in (load_cases, load_persons, load_documents, load_hypotheses,
                   load_tags_and_similar, load_timeline):
        n, e = loader(tenant_id)
        nodes.extend(n)
        edges.extend(e)
    return nodes, edges
