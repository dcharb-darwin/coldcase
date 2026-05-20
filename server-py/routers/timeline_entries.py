"""Detective-curated timeline entries + AI-suggested candidates.

Sits parallel to the audit feed: AuditEvent is the system's chronology
of state changes; TimelineEntry is the detective's chronology of the
underlying case (what happened when, who did what).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models import Case, Document, TimelineEntry, TimelineEntrySource
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
    tags=["Timeline"],
    dependencies=[Depends(enforce_vendor_scope)],
)


# ── Bodies ──────────────────────────────────────────────────────────────────


class CreateEntryBody(BaseModel):
    occurred_at: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=300)
    notes: str = ""
    source_document_id: str = ""
    # When converting an AI suggestion to a real entry, the caller can
    # echo the suggestion's rationale through so the audit trail preserves
    # the model's grounding.
    rationale: str = ""
    source: TimelineEntrySource = TimelineEntrySource.MANUAL


# ── CRUD ────────────────────────────────────────────────────────────────────


@router.get("/cases/{case_id}/timeline-entries")
@require_perm("case.read")
def list_entries(case_id: str, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    entries = TimelineEntry.objects(
        tenant_id=user.tenant_id, case=case,
    ).order_by("occurred_at", "created_at")
    return {"entries": [e.to_dict() for e in entries]}


@router.post("/cases/{case_id}/timeline-entries", status_code=201)
@require_perm("case.edit")
def create_entry(
    case_id: str, body: CreateEntryBody, user: CurrentUser = Depends(current_user),
):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    e = TimelineEntry(
        tenant_id=user.tenant_id, case=case,
        occurred_at=body.occurred_at.strip(),
        label=body.label.strip(),
        notes=body.notes.strip(),
        source_document_id=body.source_document_id.strip(),
        source=body.source.value,
        rationale=body.rationale.strip(),
        created_by=user.user_id,
    ).save()
    return e.to_dict()


@router.delete("/cases/{case_id}/timeline-entries/{entry_id}", status_code=204)
@require_perm("case.edit")
def delete_entry(
    case_id: str, entry_id: str, user: CurrentUser = Depends(current_user),
):
    e = TimelineEntry.objects(id=entry_id, tenant_id=user.tenant_id).first()
    if not e or str(e.case.id) != case_id:
        raise HTTPException(404, "Timeline entry not found")
    e.delete()
    return None


# ── AI-suggested timeline events (Phase C) ─────────────────────────────────


@router.post("/cases/{case_id}/timeline-entries/suggestions")
@require_perm("case.read")
def suggest_entries(case_id: str, user: CurrentUser = Depends(current_user)):
    """LLM-extract dated events from the case's documents. Returns
    candidates; the detective accepts/dismisses each before they become
    real TimelineEntry rows. Skips events that look like existing entries
    on the case."""
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
            snippets.append(f"=== {d.original_filename} ===\n{text[:2500]}")
    if not snippets:
        return {"suggestions": [], "reason": "No extractable document text on this case."}
    docs_block = "\n\n".join(snippets)

    existing = TimelineEntry.objects(tenant_id=user.tenant_id, case=case)
    existing_labels = {(e.label or "").strip().lower() for e in existing}

    system = (
        "Extract dated case events from cold-case investigation documents. "
        "Return a JSON array of objects with: "
        "`occurred_at` (ISO date or descriptive — \"1945-08-15\", "
        "\"1945-08-15 17:00\", or \"circa August 1945\"), "
        "`label` (one short noun-phrase under 80 chars — what happened), "
        "`notes` (one or two sentences elaborating; empty string if not needed), "
        "`source_document` (filename if identifiable, empty otherwise), and "
        "`rationale` (one short sentence under 25 words quoting or paraphrasing "
        "the document text that grounds this event). "
        "Up to 10 entries. Skip undated speculation. Prefer specificity "
        "(date + clock time when both are stated). Distinct events only — "
        "merge near-duplicates."
    )
    user_prompt = (
        f"Case: {case.case_number} — {case.title}\n"
        f"Description: {case.description or '(none)'}\n\n"
        f"Document excerpts:\n{docs_block}\n\n"
        f"Return JSON only."
    )

    try:
        provider = get_llm_provider()
        resp = provider.chat(system=system, user=user_prompt)
        raw = resp.content if hasattr(resp, "content") else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("Timeline suggestion provider failed: %s", exc)
        return {"suggestions": [], "reason": f"LLM unavailable: {exc}"}

    # Build a doc-name → id index so the UI can render a "view source" link.
    docs_by_name = {d.original_filename: str(d.id) for d in docs}

    parsed = _extract_json_list(raw)
    suggestions: list[dict] = []
    seen_labels: set[str] = set()
    for item in parsed:
        if not isinstance(item, dict):
            continue
        label = (item.get("label") or "").strip()
        occurred = (item.get("occurred_at") or "").strip()
        if not label or not occurred:
            continue
        ll = label.lower()
        if ll in existing_labels or ll in seen_labels:
            continue
        seen_labels.add(ll)
        source_doc = (item.get("source_document") or "").strip()
        suggestions.append({
            "occurred_at": occurred,
            "label": label,
            "notes": (item.get("notes") or "").strip(),
            "source_document": source_doc,
            "source_document_id": docs_by_name.get(source_doc, ""),
            "rationale": (item.get("rationale") or "").strip(),
        })
        if len(suggestions) >= 10:
            break

    return {"suggestions": suggestions, "model": getattr(resp, "model", "")}
