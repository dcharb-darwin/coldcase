"""Tag vocabulary + assignment endpoints.

Vocabulary is admin-managed; assignments are detective-managed. The
list endpoint is open to anyone with `case.read` so the picker can
populate without a privilege bump.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models import (
    Case, Document, Message, Tag, TagAssignment, TagKind, TagSubjectKind,
    Provenance, ProvenanceSource, TAG_COLOR_CHOICES,
)
from models.audit_event import AuditEventType
from models.report import Report
from providers.llm import get_llm_provider
from routers._deps import CurrentUser, current_user, require_perm
from services import case_audit
from services.document_text import extract_text
from services.vendor_scope import enforce_vendor_scope


logger = logging.getLogger(__name__)


router = APIRouter(
    tags=["Tags"],
    dependencies=[Depends(enforce_vendor_scope)],
)


# ── Bodies ──────────────────────────────────────────────────────────────────


class CreateTagBody(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    slug: str = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9][a-z0-9\-:.]*$")
    description: str = ""
    color: str = "slate"
    applicable_to: list[str] = Field(default_factory=list)


# ── Vocabulary endpoints (admin manages, everyone reads) ────────────────────


@router.get("/tags")
@require_perm("case.read")
def list_tags(user: CurrentUser = Depends(current_user)):
    """Closed agency vocabulary. Surfaces in the tag picker on every case."""
    tags = Tag.objects(tenant_id=user.tenant_id).order_by("kind", "label")
    return {"tags": [t.to_dict() for t in tags]}


@router.post("/tags", status_code=201)
@require_perm("roles.manage")  # admin-only — closed vocabulary
def create_tag(body: CreateTagBody, user: CurrentUser = Depends(current_user)):
    if body.color not in TAG_COLOR_CHOICES:
        raise HTTPException(422, f"color must be one of {TAG_COLOR_CHOICES}")
    invalid = [s for s in body.applicable_to if s not in {k.value for k in TagSubjectKind}]
    if invalid:
        raise HTTPException(422, f"applicable_to contains invalid kinds: {invalid}")
    if Tag.objects(tenant_id=user.tenant_id, slug=body.slug).first():
        raise HTTPException(409, f"Tag slug {body.slug!r} already exists")

    tag = Tag(
        tenant_id=user.tenant_id,
        label=body.label,
        slug=body.slug,
        description=body.description,
        color=body.color,
        kind=TagKind.USER.value,
        applicable_to=body.applicable_to,
        created_by=user.user_id,
    ).save()
    return tag.to_dict()


# ── Assignment endpoints (any role with case.edit) ──────────────────────────


def _ensure_subject_in_tenant(
    user: CurrentUser, subject_kind: str, subject_id: str,
) -> tuple[str | None, str | None]:
    """Validate the subject exists in this tenant and return (case_id, error).
    case_id is denormalized onto the assignment for cheap per-case queries."""
    if subject_kind == TagSubjectKind.CASE.value:
        case = Case.objects(id=subject_id, tenant_id=user.tenant_id).first()
        if not case:
            return None, "Case not found"
        return str(case.id), None
    if subject_kind == TagSubjectKind.DOCUMENT.value:
        doc = Document.objects(id=subject_id, tenant_id=user.tenant_id).first()
        if not doc:
            return None, "Document not found"
        return str(doc.case.id) if doc.case else None, None
    if subject_kind == TagSubjectKind.MESSAGE.value:
        msg = Message.objects(id=subject_id, tenant_id=user.tenant_id).first()
        if not msg:
            return None, "Message not found"
        conv = msg.conversation
        cid = str(conv.case.id) if (conv and getattr(conv, "case", None)) else None
        return cid, None
    if subject_kind == TagSubjectKind.REPORT.value:
        rep = Report.objects(id=subject_id, tenant_id=user.tenant_id).first()
        if not rep:
            return None, "Report not found"
        return str(rep.case.id) if rep.case else None, None
    return None, f"Unknown subject_kind {subject_kind!r}"


class AssignTagBody(BaseModel):
    """Optional body on the assign endpoint. Manual chip clicks omit it
    entirely; the accept-from-AI path passes provenance so the chain
    records which tags came from a model proposal."""
    source: ProvenanceSource = ProvenanceSource.MANUAL
    suggested_by_model: str = ""
    suggested_rationale: str = ""


@router.post("/tags/{tag_id}/assign/{subject_kind}/{subject_id}", status_code=201)
@require_perm("case.edit")
def assign_tag(
    tag_id: str, subject_kind: str, subject_id: str,
    body: AssignTagBody | None = None,
    user: CurrentUser = Depends(current_user),
):
    body = body or AssignTagBody()
    tag = Tag.objects(id=tag_id, tenant_id=user.tenant_id).first()
    if not tag:
        raise HTTPException(404, "Tag not found")
    if subject_kind not in {k.value for k in TagSubjectKind}:
        raise HTTPException(422, f"subject_kind must be one of {[k.value for k in TagSubjectKind]}")
    if tag.applicable_to and subject_kind not in tag.applicable_to:
        raise HTTPException(
            422,
            f"Tag {tag.slug!r} is not applicable to {subject_kind} (allowed: {tag.applicable_to})",
        )

    case_id, err = _ensure_subject_in_tenant(user, subject_kind, subject_id)
    if err:
        raise HTTPException(404, err)

    # Upsert-style: idempotent re-assign returns the existing row.
    existing = TagAssignment.objects(
        tenant_id=user.tenant_id, tag_id=tag_id,
        subject_kind=subject_kind, subject_id=subject_id,
    ).first()
    if existing:
        return existing.to_dict()

    now = datetime.utcnow()
    is_ai = body.source == ProvenanceSource.AI_SUGGESTED
    prov = Provenance(
        source=body.source.value,
        suggested_by_model=body.suggested_by_model.strip() if is_ai else "",
        suggested_rationale=body.suggested_rationale.strip() if is_ai else "",
        accepted_at=now if is_ai else None,
        accepted_by=user.user_id if is_ai else "",
    )
    ta = TagAssignment(
        tenant_id=user.tenant_id, tag_id=tag_id,
        subject_kind=subject_kind, subject_id=subject_id,
        case_id=case_id,
        applied_by=user.user_id,
        provenance=prov,
    ).save()

    if is_ai:
        case_audit.log_user_event(
            user,
            event_type=AuditEventType.TAG_ACCEPTED_FROM_AI,
            case_id=case_id,
            summary=f"Accepted AI-suggested tag #{tag.slug} on {subject_kind}",
            detail={
                "tag_id": tag_id,
                "tag_slug": tag.slug,
                "subject_kind": subject_kind,
                "subject_id": subject_id,
                "model": prov.suggested_by_model,
                "rationale": prov.suggested_rationale,
            },
        )
    # Touch the case's last-activity so the dashboard reflects the tag.
    if case_id:
        Case.objects(id=case_id).update_one(set__last_activity_at=datetime.utcnow())
    return ta.to_dict()


@router.delete("/tags/{tag_id}/assign/{subject_kind}/{subject_id}", status_code=204)
@require_perm("case.edit")
def unassign_tag(
    tag_id: str, subject_kind: str, subject_id: str,
    user: CurrentUser = Depends(current_user),
):
    deleted = TagAssignment.objects(
        tenant_id=user.tenant_id, tag_id=tag_id,
        subject_kind=subject_kind, subject_id=subject_id,
    ).delete()
    if deleted == 0:
        raise HTTPException(404, "Assignment not found")
    return None


# ── Per-case read: every tag on every artifact of this case ─────────────────


# ── AI-suggested tags (Phase C) ────────────────────────────────────────────


_JSON_BLOCK_RE = re.compile(r"\[\s*(?:\{[\s\S]*?\}\s*,?\s*)+\]")


def _extract_json_list(text: str) -> list[dict]:
    """LLM outputs JSON either bare or in a code fence. Pull the first
    `[ {...}, ... ]` block we find and parse. Returns [] on any failure
    — suggestions degrade quietly to an empty list."""
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


@router.post("/cases/{case_id}/tags/suggestions")
@require_perm("case.read")
def suggest_tags(case_id: str, user: CurrentUser = Depends(current_user)):
    """Ask the LLM to suggest 3-5 tags from the closed agency vocabulary
    that fit this case, given its documents. Returns candidates the
    detective accepts via the regular `POST /tags/{id}/assign/...` flow —
    no automatic assignment.

    Vocabulary stays closed: the model can only choose from `applicable_to`
    case-scoped tags that aren't already applied. This avoids the LLM
    inventing slugs that don't exist."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    # Build the candidate vocabulary — case-applicable, not already applied.
    case_tags = Tag.objects(tenant_id=user.tenant_id)
    already = {
        a.tag_id
        for a in TagAssignment.objects(
            tenant_id=user.tenant_id,
            subject_kind=TagSubjectKind.CASE.value,
            subject_id=case_id,
        )
    }
    vocab = [
        t for t in case_tags
        if (not t.applicable_to or TagSubjectKind.CASE.value in t.applicable_to)
        and str(t.id) not in already
    ]
    if not vocab:
        return {"suggestions": [], "reason": "No applicable tags remain — all are already applied."}

    # Compose context: case meta + a snippet of each document's first page.
    # Cap the doc snippets so the prompt stays inside any reasonable model
    # context budget; the goal is signal, not completeness.
    docs = list(Document.objects(case=case)[:8])
    snippets: list[str] = []
    for d in docs:
        try:
            text = extract_text(d)
        except Exception:  # noqa: BLE001 — never block on extraction
            text = ""
        if text:
            # Trim per-doc so a long PDF doesn't dominate the prompt budget.
            snippets.append(f"=== {d.original_filename} ===\n{text[:1500]}")
    docs_block = "\n\n".join(snippets) if snippets else "(no document text available)"

    vocab_block = "\n".join(
        f"- {t.slug} — {t.label}: {t.description or '(no description)'}"
        for t in vocab
    )
    system = (
        "You suggest tags from a closed agency vocabulary for a cold-case "
        "investigation file. You must ONLY return tags from the provided "
        "vocabulary — do not invent new tags. Return a JSON array of "
        "objects: [{\"slug\": \"…\", \"rationale\": \"…\"}]. Suggest 3 to 5 "
        "tags maximum, only the ones that clearly apply based on the case "
        "context. Leave out tags you're unsure about. Rationale must be "
        "one short sentence (under 20 words) grounded in the case text."
    )
    user_prompt = (
        f"Case: {case.case_number} — {case.title}\n"
        f"Classification: {case.classification}\n"
        f"Description: {case.description or '(none)'}\n\n"
        f"Available vocabulary:\n{vocab_block}\n\n"
        f"Document excerpts:\n{docs_block}\n\n"
        f"Return JSON only."
    )

    try:
        provider = get_llm_provider()
        resp = provider.chat(system=system, user=user_prompt)
        raw = resp.content if hasattr(resp, "content") else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tag suggestion provider failed: %s", exc)
        return {"suggestions": [], "reason": f"LLM unavailable: {exc}"}

    parsed = _extract_json_list(raw)
    by_slug = {t.slug: t for t in vocab}
    suggestions: list[dict] = []
    seen: set[str] = set()
    for item in parsed:
        if not isinstance(item, dict):
            continue
        slug = (item.get("slug") or "").strip().lower()
        rationale = (item.get("rationale") or "").strip()
        if slug in seen or slug not in by_slug:
            continue
        seen.add(slug)
        t = by_slug[slug]
        suggestions.append({
            "tag": t.to_dict(),
            "rationale": rationale or "(no rationale provided)",
        })
        if len(suggestions) >= 5:
            break

    return {"suggestions": suggestions, "model": getattr(resp, "model", ""), "raw_preview": raw[:280]}


@router.get("/cases/{case_id}/tags")
@require_perm("case.read")
def list_case_tags(case_id: str, user: CurrentUser = Depends(current_user)):
    """Returns the tags assigned anywhere within the case, grouped by subject.
    Used by the case hero + Brief tab to render chips."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    assignments = TagAssignment.objects(
        tenant_id=user.tenant_id, case_id=case_id,
    )
    tag_ids = list({a.tag_id for a in assignments})
    tags = {str(t.id): t for t in Tag.objects(tenant_id=user.tenant_id, id__in=tag_ids)}

    out: list[dict] = []
    for a in assignments:
        tag = tags.get(a.tag_id)
        if not tag:
            continue
        out.append({**a.to_dict(), "tag": tag.to_dict()})
    return {"assignments": out}
