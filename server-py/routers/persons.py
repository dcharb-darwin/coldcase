"""Persons — case-scoped suspect / witness / victim / officer entries.

Phase B endpoints: list / create / update / delete, scoped to a case.
Phase C will add AI-extracted candidates plus PersonMention linking.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import re as _re

from datetime import datetime as _datetime

from models import (
    Case, Document, Person, PersonRole,
    Provenance, ProvenanceSource,
)
from models.audit_event import AuditEventType
from providers.llm import get_llm_provider
from routers._deps import CurrentUser, current_user, require_perm
from services import case_audit
from services.document_text import extract_text
from services.vendor_scope import enforce_vendor_scope


logger = logging.getLogger(__name__)
_JSON_BLOCK_RE = re.compile(r"\[\s*(?:\{[\s\S]*?\}\s*,?\s*)+\]")


def _extract_json_list(text: str) -> list[dict]:
    if not text:
        return []
    m = _JSON_BLOCK_RE.search(text)
    if not m:
        return []
    try:
        parsed = json.loads(m.group(0))
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


router = APIRouter(
    tags=["Persons"],
    dependencies=[Depends(enforce_vendor_scope)],
)


class CreatePersonBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: PersonRole = PersonRole.OTHER
    descriptor: str = ""
    notes: str = ""
    # AI-suggestion lineage. Manual creates omit these; the accept-from-AI
    # path passes ai_suggested + model + rationale so the chain records
    # which artifacts came from an LLM proposal that the officer accepted.
    source: ProvenanceSource = ProvenanceSource.MANUAL
    suggested_by_model: str = ""
    suggested_rationale: str = ""


class UpdatePersonBody(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    role: Optional[PersonRole] = None
    descriptor: Optional[str] = None
    notes: Optional[str] = None


@router.get("/cases/{case_id}/persons")
@require_perm("case.read")
def list_persons(case_id: str, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    rows = Person.objects(tenant_id=user.tenant_id, case=case).order_by("role", "name")
    return {"persons": [p.to_dict() for p in rows]}


@router.post("/cases/{case_id}/persons", status_code=201)
@require_perm("case.edit")
def create_person(case_id: str, body: CreatePersonBody, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    now = _datetime.utcnow()
    is_ai = body.source == ProvenanceSource.AI_SUGGESTED
    prov = Provenance(
        source=body.source.value,
        suggested_by_model=body.suggested_by_model.strip() if is_ai else "",
        suggested_rationale=body.suggested_rationale.strip() if is_ai else "",
        accepted_at=now if is_ai else None,
        accepted_by=user.user_id if is_ai else "",
    )
    p = Person(
        tenant_id=user.tenant_id, case=case,
        name=body.name.strip(),
        role=body.role.value,
        descriptor=body.descriptor.strip(),
        notes=body.notes.strip(),
        created_by=user.user_id,
        provenance=prov,
    ).save()

    if is_ai:
        # Separate audit event so the chain answers "what came from AI"
        # without parsing detail blobs.
        case_audit.log_user_event(
            user,
            event_type=AuditEventType.PERSON_ACCEPTED_FROM_AI,
            case_id=case_id,
            summary=f"Accepted AI-suggested person {p.name!r} ({p.role}) onto case",
            detail={
                "person_id": str(p.id),
                "name": p.name,
                "role": p.role,
                "model": prov.suggested_by_model,
                "rationale": prov.suggested_rationale,
            },
        )
    return p.to_dict()


@router.patch("/cases/{case_id}/persons/{person_id}")
@require_perm("case.edit")
def update_person(
    case_id: str, person_id: str, body: UpdatePersonBody,
    user: CurrentUser = Depends(current_user),
):
    p = Person.objects(id=person_id, tenant_id=user.tenant_id).first()
    if not p or str(p.case.id) != case_id:
        raise HTTPException(404, "Person not found")
    if body.name is not None:
        p.name = body.name.strip()
    if body.role is not None:
        p.role = body.role.value
    if body.descriptor is not None:
        p.descriptor = body.descriptor.strip()
    if body.notes is not None:
        p.notes = body.notes.strip()
    p.save()
    return p.to_dict()


# ── Case connections graph ─────────────────────────────────────────────────


@router.get("/cases/{case_id}/connections")
@require_perm("case.read")
def case_connections(case_id: str, user: CurrentUser = Depends(current_user)):
    """Derived graph view: nodes = (this case, every person on this case,
    every other case where one of those people also appears). Edges =
    (person-on-this-case, person-on-other-case). Computed lazily — no
    new persistence — so the graph is always in sync with the underlying
    Person rows.

    Pragmatic for a single-tenant cold-case shop (<1000 persons). When
    that scales, persist edges and update them on Person create/update.
    """
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    persons_on_case = list(Person.objects(tenant_id=user.tenant_id, case=case))

    # Build normalized-name → list of (case, role, descriptor) across the
    # tenant once; then look up each person on the focal case in O(1).
    all_persons = list(
        Person.objects(tenant_id=user.tenant_id).only(
            "name", "role", "descriptor", "case",
        )
    )
    by_norm: dict[str, list] = {}
    for p in all_persons:
        if not p.case:
            continue
        by_norm.setdefault(_normalize_name(p.name), []).append(p)

    nodes: list[dict] = [{
        "id": f"case:{case_id}",
        "kind": "case",
        "case_id": case_id,
        "case_number": case.case_number,
        "case_title": case.title,
        "case_classification": case.classification,
        "focal": True,
    }]
    edges: list[dict] = []
    other_case_ids: set[str] = set()

    for p in persons_on_case:
        pnode_id = f"person:{p.id}"
        nodes.append({
            "id": pnode_id,
            "kind": "person",
            "person_id": str(p.id),
            "name": p.name,
            "role": p.role,
            "descriptor": p.descriptor,
            "ai_sourced": bool(p.provenance and p.provenance.source == "ai_suggested"),
        })
        edges.append({"from": f"case:{case_id}", "to": pnode_id, "kind": "on_case"})

        # Cross-case edges: every other Person row with the same normalized
        # name on a different case. One edge per unique other case.
        seen_other_cases: set[str] = set()
        for sib in by_norm.get(_normalize_name(p.name), []):
            ocid = str(sib.case.id)
            if ocid == case_id or ocid in seen_other_cases:
                continue
            seen_other_cases.add(ocid)
            other_case_ids.add(ocid)
            edges.append({
                "from": pnode_id,
                "to": f"case:{ocid}",
                "kind": "appears_on_other_case",
                "other_role": sib.role,
            })

    # Hydrate the other-case nodes with their human-facing fields.
    for c in Case.objects(tenant_id=user.tenant_id, id__in=list(other_case_ids)):
        nodes.append({
            "id": f"case:{c.id}",
            "kind": "case",
            "case_id": str(c.id),
            "case_number": c.case_number,
            "case_title": c.title,
            "case_classification": c.classification,
            "focal": False,
        })

    return {
        "case_id": case_id,
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "persons_on_case": len(persons_on_case),
            "connected_cases": len(other_case_ids),
            "cross_case_edges": sum(1 for e in edges if e["kind"] == "appears_on_other_case"),
        },
    }


# ── Cross-case lookup ──────────────────────────────────────────────────────


def _normalize_name(s: str) -> str:
    """Loose normalisation for cross-case matching: lower, collapse spaces,
    strip honorifics/punctuation. Catches "Dr. James M. Hinton" ≈
    "James M Hinton" and "Hinton, James" written either way."""
    s = s.strip().lower()
    s = _re.sub(r"\b(dr|mr|mrs|ms|mx|prof|rev|sgt|det|capt|lt|hon)\.?\s+", "", s)
    s = _re.sub(r"[^\w\s]+", " ", s)
    s = _re.sub(r"\s+", " ", s)
    return s.strip()


@router.get("/persons/search")
@require_perm("case.read")
def search_persons(
    name: str,
    exclude_case_id: str | None = None,
    user: CurrentUser = Depends(current_user),
):
    """Find Person rows across the tenant whose name fuzzy-matches `name`.

    Real investigative value: if a witness on case A is named "James M.
    Hinton" and the same name appears as a suspect on case B, the
    detective should see that connection. The match is intentionally
    loose — exact-case name matching would miss almost every real hit
    (honorifics, middle initials, comma-flipped surnames).
    """
    if not name.strip():
        raise HTTPException(422, "name is required")
    target = _normalize_name(name)
    if not target:
        return {"matches": []}

    # Tenant-wide scan. Person collections are typically small — sub-1000
    # rows even for a busy agency — so a Python-side normalised compare
    # beats trying to express the rules in a Mongo query.
    matches: list[dict] = []
    seen_case_ids: set[str] = set()
    rows = Person.objects(tenant_id=user.tenant_id).only(
        "name", "role", "descriptor", "case",
    )
    for p in rows:
        if _normalize_name(p.name) != target:
            continue
        if not p.case:
            continue
        cid = str(p.case.id)
        if exclude_case_id and cid == exclude_case_id:
            continue
        # One match per case — the user wants "this person appears in case
        # X", not the cartesian product of every duplicate Person row.
        if cid in seen_case_ids:
            continue
        seen_case_ids.add(cid)
        case = p.case
        matches.append({
            "case_id": cid,
            "case_number": case.case_number,
            "case_title": case.title,
            "case_classification": case.classification,
            "person_id": str(p.id),
            "name": p.name,
            "role": p.role,
            "descriptor": p.descriptor,
        })

    return {"matches": matches, "query": name, "normalized": target}


@router.delete("/cases/{case_id}/persons/{person_id}", status_code=204)
@require_perm("case.edit")
def delete_person(case_id: str, person_id: str, user: CurrentUser = Depends(current_user)):
    p = Person.objects(id=person_id, tenant_id=user.tenant_id).first()
    if not p or str(p.case.id) != case_id:
        raise HTTPException(404, "Person not found")
    p.delete()
    return None


# ── AI-suggested persons (Phase C) ─────────────────────────────────────────


_ROLE_VALUES = {r.value for r in PersonRole}


@router.post("/cases/{case_id}/persons/suggestions")
@require_perm("case.read")
def suggest_persons(case_id: str, user: CurrentUser = Depends(current_user)):
    """Ask the LLM to extract named people from this case's documents and
    classify each by role. The detective accepts/dismisses individually;
    accepted ones become real Person rows via the existing endpoint. Never
    auto-creates."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    docs = list(Document.objects(case=case)[:8])
    snippets: list[str] = []
    for d in docs:
        try:
            text = extract_text(d)
        except Exception:  # noqa: BLE001
            text = ""
        if text:
            snippets.append(f"=== {d.original_filename} ===\n{text[:2000]}")
    if not snippets:
        return {"suggestions": [], "reason": "No extractable document text on this case."}
    docs_block = "\n\n".join(snippets)

    # Avoid re-proposing people already on the case.
    existing_names = {
        (p.name or "").strip().lower()
        for p in Person.objects(tenant_id=user.tenant_id, case=case)
    }

    role_list = ", ".join(sorted(_ROLE_VALUES))
    system = (
        "Extract named individuals from cold-case investigation documents. "
        "For each distinct person mentioned, return a JSON object with: "
        "`name` (the canonical name; combine title + name where appropriate), "
        f"`role` (one of: {role_list}), "
        "`descriptor` (date of birth, alias, badge, address, or one short "
        "identifying phrase — empty string if unknown), and "
        "`rationale` (one short sentence under 20 words citing the doc/snippet "
        "that justifies the classification). "
        "Return a JSON array, up to 8 entries. Skip generic references "
        "(\"the witness\", \"officer\") that don't name a person. Use "
        "`person_of_interest` only when explicitly stated; otherwise prefer "
        "`witness` or `other` over speculating about suspects."
    )
    user_prompt = (
        f"Case: {case.case_number} — {case.title}\n"
        f"Classification: {case.classification}\n\n"
        f"Document excerpts:\n{docs_block}\n\n"
        f"Return JSON only."
    )

    try:
        provider = get_llm_provider()
        resp = provider.chat(system=system, user=user_prompt)
        raw = resp.content if hasattr(resp, "content") else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("Person suggestion provider failed: %s", exc)
        return {"suggestions": [], "reason": f"LLM unavailable: {exc}"}

    parsed = _extract_json_list(raw)
    suggestions: list[dict] = []
    seen_names: set[str] = set()
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name or name.lower() in existing_names or name.lower() in seen_names:
            continue
        role = (item.get("role") or "other").strip().lower()
        if role not in _ROLE_VALUES:
            role = "other"
        seen_names.add(name.lower())
        suggestions.append({
            "name": name,
            "role": role,
            "descriptor": (item.get("descriptor") or "").strip(),
            "rationale": (item.get("rationale") or "").strip(),
        })
        if len(suggestions) >= 8:
            break

    return {"suggestions": suggestions, "model": getattr(resp, "model", "")}
