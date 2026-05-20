"""Detective-curated freeform notes scoped to case / document / report.

Sibling to Tag (closed vocab) and TimelineEntry (dated events). Plain
markdown body. CRUD only — no AI extraction, no closed vocabulary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models import Case, Document, Note, NoteSubjectKind
from models.report import Report
from routers._deps import CurrentUser, current_user, require_perm
from services.vendor_scope import enforce_vendor_scope


router = APIRouter(
    tags=["Notes"],
    dependencies=[Depends(enforce_vendor_scope)],
)


class CreateNoteBody(BaseModel):
    subject_kind: NoteSubjectKind = NoteSubjectKind.CASE
    subject_id: str = Field(min_length=1)
    body: str = Field(min_length=1, max_length=20_000)


class UpdateNoteBody(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)


def _validate_subject(user: CurrentUser, case: Case, kind: str, subject_id: str) -> None:
    """Confirm the (kind, subject_id) belongs to this case in this tenant."""
    if kind == NoteSubjectKind.CASE.value:
        if subject_id != str(case.id):
            raise HTTPException(422, "subject_id must equal case_id for case-scoped notes")
        return
    if kind == NoteSubjectKind.DOCUMENT.value:
        d = Document.objects(id=subject_id, tenant_id=user.tenant_id).first()
        if not d or (d.case and str(d.case.id) != str(case.id)):
            raise HTTPException(404, "Document not found on this case")
        return
    if kind == NoteSubjectKind.REPORT.value:
        r = Report.objects(id=subject_id, tenant_id=user.tenant_id).first()
        if not r or (r.case and str(r.case.id) != str(case.id)):
            raise HTTPException(404, "Report not found on this case")
        return
    raise HTTPException(422, f"Unknown subject_kind {kind!r}")


@router.get("/cases/{case_id}/notes")
@require_perm("case.read")
def list_notes(
    case_id: str,
    subject_kind: Optional[NoteSubjectKind] = None,
    subject_id: Optional[str] = None,
    user: CurrentUser = Depends(current_user),
):
    """List notes on the case. Optional `subject_kind` + `subject_id`
    filter narrows to a single document/report's notes."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    q = Note.objects(tenant_id=user.tenant_id, case=case)
    if subject_kind is not None:
        q = q.filter(subject_kind=subject_kind.value)
    if subject_id is not None:
        q = q.filter(subject_id=subject_id)
    rows = q.order_by("-updated_at")
    return {"notes": [n.to_dict() for n in rows]}


@router.post("/cases/{case_id}/notes", status_code=201)
@require_perm("case.edit")
def create_note(
    case_id: str, body: CreateNoteBody, user: CurrentUser = Depends(current_user),
):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    _validate_subject(user, case, body.subject_kind.value, body.subject_id)
    n = Note(
        tenant_id=user.tenant_id, case=case,
        subject_kind=body.subject_kind.value,
        subject_id=body.subject_id,
        body=body.body.strip(),
        created_by=user.user_id, updated_by=user.user_id,
    ).save()
    return n.to_dict()


@router.patch("/cases/{case_id}/notes/{note_id}")
@require_perm("case.edit")
def update_note(
    case_id: str, note_id: str, body: UpdateNoteBody,
    user: CurrentUser = Depends(current_user),
):
    n = Note.objects(id=note_id, tenant_id=user.tenant_id).first()
    if not n or str(n.case.id) != case_id:
        raise HTTPException(404, "Note not found")
    n.body = body.body.strip()
    n.updated_by = user.user_id
    n.updated_at = datetime.utcnow()
    n.save()
    return n.to_dict()


@router.delete("/cases/{case_id}/notes/{note_id}", status_code=204)
@require_perm("case.edit")
def delete_note(case_id: str, note_id: str, user: CurrentUser = Depends(current_user)):
    n = Note.objects(id=note_id, tenant_id=user.tenant_id).first()
    if not n or str(n.case.id) != case_id:
        raise HTTPException(404, "Note not found")
    n.delete()
    return None
