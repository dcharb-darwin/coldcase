"""F3 — Promote AI output → official report → sign → export.

This router implements the §13663 path. Key invariants enforced here:
  - Once a Message is promoted to a Report, it becomes the §13663(b) "first
    draft" and cannot be mutated.
  - A Report cannot be exported until §13663(a)(2) signature is applied.
  - The signed PDF carries the verbatim §13663(a)(1) disclosure on every page
    and lists the AI program(s) used.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from lib.hash import hash_text
from models import Case, Conversation, Message, MessageRole
from models.audit_event import AuditEventType
from models.report import Report, ReportStatus, AIProgram, OfficerSignature, ReportRevision
from routers._deps import CurrentUser, current_user
from services import case_audit
from services.report_export import export_report_pdf


router = APIRouter(prefix="/reports", tags=["Reports"])


# ── Bodies ──────────────────────────────────────────────────────────────────


class PromoteBody(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    message_id: str = Field(min_length=1)
    # Officer can pre-edit before signing, but the source message is what gets
    # locked as the §13663(b) first draft.
    initial_final_text: Optional[str] = None


class EditReportBody(BaseModel):
    title: Optional[str] = None
    final_text: Optional[str] = None
    # Caller can declare additional AI programs that contributed beyond the
    # first-draft message's model (e.g., a separate summarizer ran on a doc).
    additional_ai_programs: list[dict] = Field(default_factory=list)


class SignBody(BaseModel):
    badge_number: str = ""
    display_name: str = ""
    attestation_text: Optional[str] = None


class ExportBody(BaseModel):
    target: str = "file"  # "file" | "evidence.com" (latter is Phase 2)


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/promote", status_code=201)
def promote_message_to_report(body: PromoteBody, user: CurrentUser = Depends(current_user)):
    """Take an assistant Message and create a Report whose §13663(b) 'first
    draft' is that Message. The message becomes immutable."""
    msg = Message.objects(id=body.message_id, tenant_id=user.tenant_id).first()
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg.role != MessageRole.ASSISTANT.value:
        raise HTTPException(422, "Only assistant messages can be promoted to a §13663 first draft")
    if msg.is_first_ai_draft:
        raise HTTPException(409, "This message is already the first draft of another report")

    conv = msg.conversation
    case = conv.case

    # Capture the AI program from the message itself. Additional programs can
    # be added at edit time.
    programs: list[AIProgram] = []
    if msg.model or msg.provider:
        programs.append(AIProgram(
            name=msg.provider or "unknown-provider",
            version=msg.model or "",
            provider=msg.provider or "",
        ))

    now = datetime.utcnow()
    final_text = body.initial_final_text or msg.content
    initial_revision = ReportRevision(
        seq=0,
        text=msg.content,
        editor_id="ai",
        editor_display=f"{msg.provider}:{msg.model}" if msg.provider else "ai",
        timestamp=now,
        content_sha256=hash_text(msg.content),
        byte_count=len(msg.content.encode("utf-8")),
        note="AI first draft (verbatim — §13663(b))",
    )
    revisions = [initial_revision]
    if final_text != msg.content:
        revisions.append(ReportRevision(
            seq=1,
            text=final_text,
            editor_id=user.user_id,
            editor_display=user.display_name or user.user_id,
            timestamp=now,
            content_sha256=hash_text(final_text),
            byte_count=len(final_text.encode("utf-8")),
            note="initial officer override at promote-time",
        ))

    report = Report(
        tenant_id=user.tenant_id, case=case, conversation=conv,
        title=body.title,
        final_text=final_text,
        first_ai_draft_message_id=str(msg.id),
        first_ai_draft_text_snapshot=msg.content,
        ai_programs_used=programs,
        status=ReportStatus.DRAFT.value,
        revisions=revisions,
        created_by=user.user_id,
    ).save()

    # Lock the message as the §13663(b) first draft.
    msg.is_first_ai_draft = True
    msg.first_draft_locked_for_report_id = str(report.id)
    msg.save()

    case_audit.log(
        tenant_id=user.tenant_id, user_id=user.user_id,
        user_display=user.display_name, ip_address=user.ip_address,
        event_type=AuditEventType.REPORT_DRAFTED,
        case_id=str(case.id), conversation_id=str(conv.id),
        message_id=str(msg.id), report_id=str(report.id),
        summary=f"Promoted assistant message to report {body.title!r}",
        detail={
            "model": msg.model, "provider": msg.provider,
            "first_ai_draft_hash": hash_text(msg.content),
        },
    )
    return report.to_dict()


@router.get("/{report_id}")
def get_report(report_id: str, user: CurrentUser = Depends(current_user)):
    report = Report.objects(id=report_id, tenant_id=user.tenant_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    return report.to_dict()


@router.patch("/{report_id}")
def edit_report(report_id: str, body: EditReportBody, user: CurrentUser = Depends(current_user)):
    report = Report.objects(id=report_id, tenant_id=user.tenant_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    if report.status != ReportStatus.DRAFT.value:
        raise HTTPException(409, f"Cannot edit a report in status {report.status!r}")

    if body.title is not None:
        report.title = body.title

    text_changed = body.final_text is not None and body.final_text != report.final_text
    if text_changed:
        report.final_text = body.final_text
        next_seq = (max((r.seq for r in (report.revisions or [])), default=-1)) + 1
        report.revisions.append(ReportRevision(
            seq=next_seq,
            text=body.final_text,
            editor_id=user.user_id,
            editor_display=user.display_name or user.user_id,
            timestamp=datetime.utcnow(),
            content_sha256=hash_text(body.final_text),
            byte_count=len(body.final_text.encode("utf-8")),
            note="officer edit",
        ))

    if body.additional_ai_programs:
        existing_keys = {(p.name, p.version) for p in (report.ai_programs_used or [])}
        for entry in body.additional_ai_programs:
            key = (entry.get("name", ""), entry.get("version", ""))
            if key in existing_keys or not entry.get("name"):
                continue
            report.ai_programs_used.append(AIProgram(
                name=entry["name"],
                version=entry.get("version", ""),
                provider=entry.get("provider", ""),
            ))
    report.save()

    if text_changed:
        case_audit.log(
            tenant_id=user.tenant_id, user_id=user.user_id,
            user_display=user.display_name, ip_address=user.ip_address,
            event_type=AuditEventType.REPORT_EDITED,
            case_id=str(report.case.id), report_id=str(report.id),
            summary=f"Revision {report.revisions[-1].seq} of {report.title!r}",
            detail={
                "revision_seq": report.revisions[-1].seq,
                "content_sha256": report.revisions[-1].content_sha256,
                "byte_count": report.revisions[-1].byte_count,
            },
        )
    return report.to_dict()


@router.post("/{report_id}/sign")
def sign_report(report_id: str, body: SignBody, user: CurrentUser = Depends(current_user)):
    """§13663(a)(2). Apply officer e-signature. After this, the Report is immutable."""
    report = Report.objects(id=report_id, tenant_id=user.tenant_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    if report.status != ReportStatus.DRAFT.value:
        raise HTTPException(409, f"Cannot sign a report in status {report.status!r}")
    if not (report.ai_programs_used and any(p.name for p in report.ai_programs_used)):
        raise HTTPException(
            422,
            "At least one AI program must be identified before signing — "
            "Penal Code §13663(a)(1) requires identification of the AI program(s) used.",
        )
    if not (report.final_text or "").strip():
        raise HTTPException(422, "Report final_text is empty")

    now = datetime.utcnow()
    content_hash = hash_text(report.final_text)
    sig = OfficerSignature(
        user_id=user.user_id,
        display_name=body.display_name or user.display_name or user.user_id,
        badge_number=body.badge_number,
        signed_at=now,
        ip_address=user.ip_address,
        content_sha256=content_hash,
        attestation_text=body.attestation_text or OfficerSignature.attestation_text.default,
    )
    report.signature = sig
    report.signed_at = now
    report.status = ReportStatus.SIGNED.value
    report.save()

    case_audit.log(
        tenant_id=user.tenant_id, user_id=user.user_id,
        user_display=user.display_name, ip_address=user.ip_address,
        event_type=AuditEventType.REPORT_SIGNED,
        case_id=str(report.case.id), report_id=str(report.id),
        summary=f"Signed report {report.title!r}",
        detail={
            "content_sha256": content_hash,
            "ai_programs": [
                {"name": p.name, "version": p.version, "provider": p.provider}
                for p in report.ai_programs_used
            ],
        },
    )
    return report.to_dict()


@router.post("/{report_id}/export")
def export_report(report_id: str, body: ExportBody, user: CurrentUser = Depends(current_user)):
    """Render the signed report to PDF (with §13663(a)(1) disclosure on every
    page) and record the export. The 'evidence.com' target is Phase 2."""
    report = Report.objects(id=report_id, tenant_id=user.tenant_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    if report.status not in (ReportStatus.SIGNED.value, ReportStatus.EXPORTED.value):
        raise HTTPException(
            422,
            "Report must be signed before export — Penal Code §13663(a)(2) "
            "requires the officer's signature.",
        )
    if body.target not in ("file", "evidence.com"):
        raise HTTPException(422, "Unsupported export target")
    if body.target == "evidence.com":
        raise HTTPException(501, "evidence.com integration is Phase 2 — use target=file for now")

    pdf_path = export_report_pdf(report)
    report.exported_artifact_uri = f"file://{pdf_path}"
    report.export_target = body.target
    report.exported_at = datetime.utcnow()
    report.status = ReportStatus.EXPORTED.value
    report.save()

    case_audit.log(
        tenant_id=user.tenant_id, user_id=user.user_id,
        user_display=user.display_name, ip_address=user.ip_address,
        event_type=AuditEventType.REPORT_EXPORTED,
        case_id=str(report.case.id), report_id=str(report.id),
        summary=f"Exported report {report.title!r} to {body.target}",
        detail={"artifact_uri": report.exported_artifact_uri},
    )
    return report.to_dict()


@router.get("/{report_id}/pdf")
def download_report_pdf(report_id: str, user: CurrentUser = Depends(current_user)):
    """Stream the signed-and-exported PDF. The canonical artifact under
    business rule #14 — retained as long as the Report retention holds."""
    import os
    report = Report.objects(id=report_id, tenant_id=user.tenant_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    if not report.exported_artifact_uri:
        raise HTTPException(409, "Report has not been exported yet")
    path = report.exported_artifact_uri.replace("file://", "")
    if not os.path.isabs(path):
        path = os.path.join(os.environ.get("UPLOAD_DIRECTORY", "./uploads"), path)
    if not os.path.exists(path):
        raise HTTPException(404, f"Artifact missing on disk at {path}")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{report.title or report.id}.pdf",
    )


@router.get("/cases/{case_id}/reports")
def list_reports_for_case(case_id: str, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    reports = Report.objects(case=case).order_by("-created_at")
    return {"reports": [r.to_dict() for r in reports]}
