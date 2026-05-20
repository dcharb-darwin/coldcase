"""Tag vocabulary + assignment endpoints.

Vocabulary is admin-managed; assignments are detective-managed. The
list endpoint is open to anyone with `case.read` so the picker can
populate without a privilege bump.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models import (
    Case, Document, Message, Tag, TagAssignment, TagKind, TagSubjectKind,
    TAG_COLOR_CHOICES,
)
from models.report import Report
from routers._deps import CurrentUser, current_user, require_perm
from services.vendor_scope import enforce_vendor_scope


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


@router.post("/tags/{tag_id}/assign/{subject_kind}/{subject_id}", status_code=201)
@require_perm("case.edit")
def assign_tag(
    tag_id: str, subject_kind: str, subject_id: str,
    user: CurrentUser = Depends(current_user),
):
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

    ta = TagAssignment(
        tenant_id=user.tenant_id, tag_id=tag_id,
        subject_kind=subject_kind, subject_id=subject_id,
        case_id=case_id,
        applied_by=user.user_id,
    ).save()
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
