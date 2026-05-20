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

from models import Case, Document, Person, PersonRole
from providers.llm import get_llm_provider
from routers._deps import CurrentUser, current_user, require_perm
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
    p = Person(
        tenant_id=user.tenant_id, case=case,
        name=body.name.strip(),
        role=body.role.value,
        descriptor=body.descriptor.strip(),
        notes=body.notes.strip(),
        created_by=user.user_id,
    ).save()
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
