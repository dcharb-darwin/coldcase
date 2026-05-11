"""F1 — Case workspace + Document/MediaInput registration."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models import (
    Case, CaseStatus, CaseClassification, RetentionPolicy,
    Document, MediaInput, MediaSourceType,
)
from models.audit_event import AuditEventType
from providers.document_storage import get_document_storage_provider
from routers._deps import CurrentUser, current_user
from services import case_audit


router = APIRouter(prefix="/cases", tags=["Cases"])


# ── Pydantic bodies (module-scope — see gotchas) ────────────────────────────


class CreateCaseBody(BaseModel):
    case_number: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=300)
    classification: CaseClassification = CaseClassification.OTHER
    retention_policy: RetentionPolicy = RetentionPolicy.MATCH_OFFICIAL_REPORT
    description: str = ""
    co_investigator_ids: list[str] = Field(default_factory=list)


class UpdateCaseBody(BaseModel):
    title: Optional[str] = None
    classification: Optional[CaseClassification] = None
    retention_policy: Optional[RetentionPolicy] = None
    description: Optional[str] = None
    co_investigator_ids: Optional[list[str]] = None
    status: Optional[CaseStatus] = None


class RegisterDocumentBody(BaseModel):
    storage_uri: str = Field(min_length=1)
    original_filename: str = Field(min_length=1)
    mime_type: str = "application/pdf"
    # Optional: caller-supplied hash. If absent and the provider can resolve
    # the URI, we'll compute it. If neither, we 422.
    sha256: Optional[str] = None
    page_count: int = 0
    size_bytes: int = 0


class RegisterMediaBody(BaseModel):
    storage_uri: str = Field(min_length=1)
    source_type: MediaSourceType
    sha256: Optional[str] = None
    duration_seconds: int = 0
    captured_at: Optional[datetime] = None
    description: str = ""


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("")
def list_cases(user: CurrentUser = Depends(current_user)):
    cases = Case.objects(tenant_id=user.tenant_id).order_by("-last_activity_at")
    return {"cases": [c.to_dict() for c in cases]}


@router.post("", status_code=201)
def create_case(body: CreateCaseBody, user: CurrentUser = Depends(current_user)):
    if Case.objects(tenant_id=user.tenant_id, case_number=body.case_number).first():
        raise HTTPException(409, f"Case number {body.case_number!r} already exists")

    # Homicide → suggest indefinite if caller didn't specify a non-default.
    retention = body.retention_policy
    if (body.classification == CaseClassification.HOMICIDE
            and retention == RetentionPolicy.MATCH_OFFICIAL_REPORT):
        retention = RetentionPolicy.INDEFINITE

    case = Case(
        tenant_id=user.tenant_id,
        case_number=body.case_number,
        title=body.title,
        classification=body.classification.value,
        retention_policy=retention.value,
        description=body.description,
        primary_investigator_id=user.user_id,
        co_investigator_ids=body.co_investigator_ids,
        created_by=user.user_id,
    ).save()

    case_audit.log(
        tenant_id=user.tenant_id, user_id=user.user_id,
        user_display=user.display_name, ip_address=user.ip_address,
        event_type=AuditEventType.CASE_CREATED,
        case_id=str(case.id),
        summary=f"Created case {case.case_number}: {case.title}",
        detail={"classification": case.classification, "retention_policy": case.retention_policy},
    )
    return case.to_dict()


@router.get("/{case_id}")
def get_case(case_id: str, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    documents = Document.objects(case=case).order_by("-uploaded_at")
    media = MediaInput.objects(case=case).order_by("-registered_at")
    return {
        "case": case.to_dict(),
        "documents": [d.to_dict() for d in documents],
        "media": [m.to_dict() for m in media],
    }


@router.patch("/{case_id}")
def update_case(case_id: str, body: UpdateCaseBody, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    changes: dict = {}
    if body.title is not None:
        changes["title"] = (case.title, body.title); case.title = body.title
    if body.classification is not None:
        changes["classification"] = (case.classification, body.classification.value)
        case.classification = body.classification.value
    if body.retention_policy is not None:
        changes["retention_policy"] = (case.retention_policy, body.retention_policy.value)
        case.retention_policy = body.retention_policy.value
    if body.description is not None:
        case.description = body.description
    if body.co_investigator_ids is not None:
        case.co_investigator_ids = body.co_investigator_ids
    if body.status is not None:
        changes["status"] = (case.status, body.status.value)
        case.status = body.status.value
        if body.status == CaseStatus.CLOSED:
            case.closed_at = datetime.utcnow()
            case.closed_by = user.user_id

    case.last_activity_at = datetime.utcnow()
    case.save()

    event_type = AuditEventType.CASE_UPDATED
    if body.status == CaseStatus.CLOSED:
        event_type = AuditEventType.CASE_CLOSED
    elif body.status == CaseStatus.REOPENED:
        event_type = AuditEventType.CASE_REOPENED
    elif "retention_policy" in changes:
        event_type = AuditEventType.RETENTION_CHANGED

    case_audit.log(
        tenant_id=user.tenant_id, user_id=user.user_id,
        user_display=user.display_name, ip_address=user.ip_address,
        event_type=event_type,
        case_id=str(case.id),
        summary=f"Updated case {case.case_number}",
        detail={"changes": {k: {"from": v[0], "to": v[1]} for k, v in changes.items()}},
    )
    return case.to_dict()


# ── Documents ───────────────────────────────────────────────────────────────


@router.post("/{case_id}/documents", status_code=201)
def register_document(case_id: str, body: RegisterDocumentBody, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    sha256 = body.sha256
    size_bytes = body.size_bytes
    if not sha256:
        storage = get_document_storage_provider()
        try:
            head = storage.head(body.storage_uri)
        except FileNotFoundError as exc:
            raise HTTPException(422, str(exc))
        sha256 = head.sha256
        size_bytes = head.size_bytes or body.size_bytes

    document = Document(
        tenant_id=user.tenant_id,
        case=case,
        storage_uri=body.storage_uri,
        sha256=sha256,
        original_filename=body.original_filename,
        mime_type=body.mime_type,
        page_count=body.page_count,
        size_bytes=size_bytes,
        uploaded_by=user.user_id,
    ).save()

    case.last_activity_at = datetime.utcnow()
    case.save()

    case_audit.log(
        tenant_id=user.tenant_id, user_id=user.user_id,
        user_display=user.display_name, ip_address=user.ip_address,
        event_type=AuditEventType.DOCUMENT_REGISTERED,
        case_id=str(case.id), document_id=str(document.id),
        summary=f"Registered {document.original_filename}",
        detail={"sha256": document.sha256, "size_bytes": document.size_bytes},
    )
    return document.to_dict()


@router.get("/{case_id}/documents")
def list_documents(case_id: str, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    docs = Document.objects(case=case).order_by("-uploaded_at")
    return {"documents": [d.to_dict() for d in docs]}


@router.get("/{case_id}/documents/{doc_id}/text")
def get_document_text(case_id: str, doc_id: str, user: CurrentUser = Depends(current_user)):
    """Extract and return the document's text content for inline display.
    Mirrors what the LLM would see when the document is added to context.
    For PDFs the extraction is best-effort via pypdf; non-PDFs return raw bytes
    decoded as utf-8 with replacement on errors.
    """
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    doc = Document.objects(id=doc_id, case=case).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    from services.document_text import extract_text
    text = extract_text(doc)
    if not text:
        raise HTTPException(404, f"Could not extract text from {doc.original_filename}")
    lines = text.splitlines()
    return {"document": doc.to_dict(), "text": text, "lines": lines, "line_count": len(lines)}


# ── Media inputs ────────────────────────────────────────────────────────────


@router.post("/{case_id}/media", status_code=201)
def register_media(case_id: str, body: RegisterMediaBody, user: CurrentUser = Depends(current_user)):
    """§13663(c)(2) — any video/audio used as AI input must be in the audit trail."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    sha256 = body.sha256
    if not sha256:
        storage = get_document_storage_provider()
        try:
            head = storage.head(body.storage_uri)
            sha256 = head.sha256
        except FileNotFoundError:
            # For remote media the caller should supply the hash. We refuse
            # rather than store an unverified pointer.
            raise HTTPException(
                422,
                "sha256 is required when the media is not resolvable by the storage provider",
            )

    media = MediaInput(
        tenant_id=user.tenant_id, case=case,
        storage_uri=body.storage_uri, sha256=sha256,
        source_type=body.source_type.value,
        duration_seconds=body.duration_seconds,
        captured_at=body.captured_at,
        description=body.description,
        registered_by=user.user_id,
    ).save()

    case.last_activity_at = datetime.utcnow()
    case.save()

    case_audit.log(
        tenant_id=user.tenant_id, user_id=user.user_id,
        user_display=user.display_name, ip_address=user.ip_address,
        event_type=AuditEventType.MEDIA_REGISTERED,
        case_id=str(case.id), media_id=str(media.id),
        summary=f"Registered media ({media.source_type})",
        detail={"sha256": media.sha256, "duration_s": media.duration_seconds},
    )
    return media.to_dict()


@router.get("/{case_id}/media")
def list_media(case_id: str, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    media = MediaInput.objects(case=case).order_by("-registered_at")
    return {"media": [m.to_dict() for m in media]}
