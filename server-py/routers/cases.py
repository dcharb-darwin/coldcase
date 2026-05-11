"""F1 — Case workspace + Document/MediaInput registration."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from models import (
    Case, CaseStatus, CaseClassification, RetentionPolicy,
    Document, MediaInput, MediaSourceType,
)
from models.audit_event import AuditEventType
from providers.document_storage import get_document_storage_provider
from routers._deps import CurrentUser, current_user, require_perm
from services import case_audit
from services.vendor_scope import enforce_vendor_scope


router = APIRouter(
    prefix="/cases", tags=["Cases"],
    dependencies=[Depends(enforce_vendor_scope)],
)


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
@require_perm("case.read")
def list_cases(user: CurrentUser = Depends(current_user)):
    cases = Case.objects(tenant_id=user.tenant_id).order_by("-last_activity_at")
    return {"cases": [c.to_dict() for c in cases]}


@router.post("", status_code=201)
@require_perm("case.create")
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
@require_perm("case.read")
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
@require_perm("case.edit")
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


MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB; raise once real blob storage is wired.


def _create_document_for_case(
    *, case: Case, user: CurrentUser,
    storage_uri: str, sha256: str, size_bytes: int,
    original_filename: str, mime_type: str, page_count: int,
    audit_source: str,
) -> Document:
    """Persist a Document pointer, bump the case's last-activity, and emit
    DOCUMENT_REGISTERED. Shared between the pointer-only registration path
    and the multipart upload path."""
    document = Document(
        tenant_id=user.tenant_id, case=case,
        storage_uri=storage_uri, sha256=sha256, size_bytes=size_bytes,
        original_filename=original_filename, mime_type=mime_type,
        page_count=page_count, uploaded_by=user.user_id,
    ).save()
    case.last_activity_at = datetime.utcnow()
    case.save()
    case_audit.log_user_event(
        user,
        event_type=AuditEventType.DOCUMENT_REGISTERED,
        case_id=str(case.id), document_id=str(document.id),
        summary=f"{audit_source.title()} {original_filename}",
        detail={
            "sha256": sha256, "size_bytes": size_bytes,
            "storage_uri": storage_uri, "source": audit_source,
        },
    )
    return document


def _count_pdf_pages(data: bytes) -> int:
    """Best-effort PDF page count; returns 0 on parse failure rather
    than blocking the upload."""
    try:
        from io import BytesIO
        from pypdf import PdfReader
        return len(PdfReader(BytesIO(data)).pages)
    except Exception:  # noqa: BLE001
        return 0


@router.post("/{case_id}/documents", status_code=201)
@require_perm("document.register")
def register_document(case_id: str, body: RegisterDocumentBody, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    sha256 = body.sha256
    size_bytes = body.size_bytes
    if not sha256:
        try:
            head = get_document_storage_provider().head(body.storage_uri)
        except FileNotFoundError as exc:
            raise HTTPException(422, str(exc))
        sha256 = head.sha256
        size_bytes = head.size_bytes or body.size_bytes

    return _create_document_for_case(
        case=case, user=user,
        storage_uri=body.storage_uri, sha256=sha256, size_bytes=size_bytes,
        original_filename=body.original_filename, mime_type=body.mime_type,
        page_count=body.page_count, audit_source="registered",
    ).to_dict()


@router.post("/{case_id}/documents/upload", status_code=201)
@require_perm("document.register")
def upload_document(
    case_id: str,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(current_user),
):
    """Multipart upload path: accepts the binary, writes it through the
    artifact store, and registers the Document. Used by the in-app file
    picker for dev/demo and small-agency single-tenant deployments. For
    production, customers point PROVIDER_DOCUMENT_STORAGE at their own
    blob storage and use `register_document` against pre-existing URIs."""
    from lib.hash import sha256_bytes
    from services.artifact_store import get_artifact_store

    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_BYTES} bytes")
    if not data:
        raise HTTPException(422, "Empty upload")

    sha = sha256_bytes(data)
    mime = file.content_type or "application/octet-stream"
    # Strip any directory components from the client-supplied filename
    # before it lands in our artifact key.
    safe_name = PurePosixPath(file.filename or "upload.bin").name
    stored = get_artifact_store().put(
        f"documents/{case.id}/{sha}-{safe_name}", data, content_type=mime,
    )

    return _create_document_for_case(
        case=case, user=user,
        storage_uri=stored.uri, sha256=sha, size_bytes=len(data),
        original_filename=safe_name, mime_type=mime,
        page_count=_count_pdf_pages(data) if mime == "application/pdf" else 0,
        audit_source="uploaded",
    ).to_dict()


@router.get("/{case_id}/documents")
@require_perm("case.read")
def list_documents(case_id: str, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    docs = Document.objects(case=case).order_by("-uploaded_at")
    return {"documents": [d.to_dict() for d in docs]}


@router.get("/{case_id}/documents/{doc_id}/text")
@require_perm("case.read")
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

    from services.document_text import extract_text, text_status
    text = extract_text(doc)
    if not text:
        raise HTTPException(404, f"Could not extract text from {doc.original_filename}")
    lines = text.splitlines()
    status = text_status(doc)
    return {
        "document": doc.to_dict(),
        "text": text,
        "lines": lines,
        "line_count": len(lines),
        "extraction_method": status["method"],
    }


@router.get("/{case_id}/documents/{doc_id}/text-status")
@require_perm("case.read")
def get_document_text_status(case_id: str, doc_id: str, user: CurrentUser = Depends(current_user)):
    """Lightweight status for the document sidebar badge. Triggers extraction
    if cold, but result is cached after first call per immutable (id, sha256)."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    doc = Document.objects(id=doc_id, case=case).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    from services.document_text import text_status
    return {"document_id": str(doc.id), "filename": doc.original_filename, **text_status(doc)}


# ── Media inputs ────────────────────────────────────────────────────────────


@router.post("/{case_id}/media", status_code=201)
@require_perm("media.register")
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
@require_perm("case.read")
def list_media(case_id: str, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    media = MediaInput.objects(case=case).order_by("-registered_at")
    return {"media": [m.to_dict() for m in media]}


# ── F8 — Discovery Package ──────────────────────────────────────────────────


class DiscoveryPackageBody(BaseModel):
    reason: str = Field(min_length=1, max_length=300)
    report_ids: list[str] = Field(default_factory=list)
    include_source_binaries: bool = False


@router.post("/{case_id}/discovery-package", status_code=201)
@require_perm("case.export")
def export_discovery_package(case_id: str, body: DiscoveryPackageBody, user: CurrentUser = Depends(current_user)):
    """F8 — one-click discovery bundle. Records-officer / city-attorney
    workflow, gated by `case.export` in production (MVP: open to all
    authenticated users with case access)."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    from services.discovery_package import build_discovery_zip
    result = build_discovery_zip(
        case,
        requesting_user_id=user.user_id,
        requesting_user_display=user.display_name or user.user_id,
        reason=body.reason,
        report_ids=body.report_ids or None,
        include_source_binaries=body.include_source_binaries,
    )

    case_audit.log(
        tenant_id=user.tenant_id, user_id=user.user_id,
        user_display=user.display_name, ip_address=user.ip_address,
        event_type=AuditEventType.CASE_DISCOVERY_EXPORTED,
        case_id=str(case.id),
        summary=f"Discovery package exported ({result['report_count']} reports, {result['file_count']} files)",
        detail={
            "reason": body.reason,
            "report_ids": body.report_ids,
            "manifest_sha256": result["manifest_sha256"],
            "zip_sha256": result["zip_sha256"],
            "zip_size_bytes": result["zip_size_bytes"],
            "include_source_binaries": body.include_source_binaries,
        },
    )
    return result


@router.get("/{case_id}/audit-manifest.pdf")
@require_perm("audit.read")
def download_case_audit_manifest(case_id: str, user: CurrentUser = Depends(current_user)):
    """F15 — Per-case audit manifest PDF. Sibling to F7 (per-report chain).
    Cached on disk; regenerated only if the case has had activity since the
    cached file was written."""
    import os
    from datetime import datetime
    from fastapi.responses import FileResponse
    from services.case_manifest_export import export_case_manifest_pdf

    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    cached_path = os.path.join(
        os.environ.get("UPLOAD_DIRECTORY", "./uploads"), "manifests",
        f"{case.id}.manifest.pdf",
    )
    fresh = False
    if os.path.exists(cached_path):
        mtime = datetime.utcfromtimestamp(os.path.getmtime(cached_path))
        if case.last_activity_at and case.last_activity_at <= mtime:
            fresh = True

    path = cached_path if fresh else export_case_manifest_pdf(case)
    return FileResponse(path, media_type="application/pdf",
                        filename=f"{case.case_number}.audit-manifest.pdf")


@router.get("/{case_id}/discovery-package/{zip_filename}")
@require_perm("case.export")
def download_discovery_package(case_id: str, zip_filename: str, user: CurrentUser = Depends(current_user)):
    """Stream a previously-generated discovery ZIP. In production this is
    replaced by a customer-storage signed URL with 1h TTL (rule #21)."""
    import os
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    upload_dir = os.environ.get("UPLOAD_DIRECTORY", "./uploads")
    path = os.path.join(upload_dir, "discovery", zip_filename)
    if not os.path.exists(path) or "/" in zip_filename or ".." in zip_filename:
        raise HTTPException(404, "Discovery package not found")
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type="application/zip", filename=zip_filename)
