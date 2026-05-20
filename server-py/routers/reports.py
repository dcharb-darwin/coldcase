"""F3 — Promote AI output → official report → sign → export.

This router implements the §13663 path. Key invariants enforced here:
  - Once a Message is promoted to a Report, it becomes the §13663(b) "first
    draft" and cannot be mutated.
  - A Report cannot be exported until §13663(a)(2) signature is applied.
  - The signed PDF carries the verbatim §13663(a)(1) disclosure on every page
    and lists the AI program(s) used.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from lib.hash import hash_text
from models import Case, Conversation, Message, MessageRole
from models.audit_event import AuditEventType
from models.report import (
    AIProgram, AI_EDITOR_ID, OfficerSignature, Report, ReportRevision, ReportStatus,
    REVISION_NOTE_AI_FIRST_DRAFT, REVISION_NOTE_INITIAL_OVERRIDE, REVISION_NOTE_OFFICER_EDIT,
)
from routers._deps import CurrentUser, current_user, require_perm
from services import case_audit, external_id as ext_id
from services.chain_export import export_chain_pdf
from services.diff_export import compute_diff, export_diff_pdf
from services.report_export import export_report_pdf
from services.vendor_scope import enforce_vendor_scope


router = APIRouter(
    prefix="/reports", tags=["Reports"],
    dependencies=[Depends(enforce_vendor_scope)],
)


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
    """§13663(a)(2) hardening (F19): the officer's name + user_id come from
    the authenticated UserContext on the server, NOT from this body. Only
    badge_number (paired with user_id in the audit log so any mismatch is
    reviewable) and an optional attestation_text override are body-controlled."""
    badge_number: str = ""
    attestation_text: Optional[str] = None


class ExportBody(BaseModel):
    target: str = "file"  # "file" | "evidence.com" (latter is Phase 2)


class ReviseBody(BaseModel):
    """Ask the LLM to propose a revised draft. The response is returned to
    the client without persisting — the officer reviews + accepts via the
    regular edit endpoint, which is what creates the audit-logged revision.
    The §13663 chain stays intact: this endpoint just produces a proposal."""
    instruction: str = Field(min_length=1, max_length=2000)
    selected_text: Optional[str] = None  # if present, AI is asked to rewrite just this span


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/promote", status_code=201)
@require_perm("report.draft")
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
        editor_id=AI_EDITOR_ID,
        editor_display=f"{msg.provider}:{msg.model}" if msg.provider else AI_EDITOR_ID,
        timestamp=now,
        content_sha256=hash_text(msg.content),
        byte_count=len(msg.content.encode("utf-8")),
        note=REVISION_NOTE_AI_FIRST_DRAFT,
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
            note=REVISION_NOTE_INITIAL_OVERRIDE,
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
    # Stamp the federated-system id once the saved id exists.
    if case.external_id:
        report.external_id = ext_id.for_report(case.external_id, str(report.id))
        report.save()

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
@require_perm("case.read")
def get_report(report_id: str, user: CurrentUser = Depends(current_user)):
    report = Report.objects(id=report_id, tenant_id=user.tenant_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    return report.to_dict()


@router.patch("/{report_id}")
@require_perm("report.draft")
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
            note=REVISION_NOTE_OFFICER_EDIT,
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


@router.post("/{report_id}/revise")
@require_perm("report.draft")
def revise_report(report_id: str, body: ReviseBody, user: CurrentUser = Depends(current_user)):
    """Ask the LLM to propose a revised version of the draft (whole text or
    a selected span). The response is NOT persisted — the officer reviews
    the proposal in the UI, edits if needed, and accepts via PATCH to log
    a normal revision. The §13663(b) first draft is never touched.

    Records an AI program against the report so the §13663(a)(1) disclosure
    reflects every model that contributed."""
    from models import Document
    from providers.llm import get_llm_provider

    report = Report.objects(id=report_id, tenant_id=user.tenant_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    if report.status != ReportStatus.DRAFT.value:
        raise HTTPException(409, f"Cannot revise a report in status {report.status!r}")

    docs = list(Document.objects(case=report.case))
    doc_summary = (
        "\n".join(f"- {d.original_filename}" for d in docs)
        or "(no documents on case)"
    )

    if body.selected_text:
        scope = (
            "The officer selected the following span of the draft and wants "
            "you to rewrite ONLY that span according to the instruction. "
            "Return only the replacement text for the selected span — no "
            "preamble, no quotes around it.\n\n"
            f"=== SELECTED SPAN ===\n{body.selected_text}\n=== END SELECTED ===\n"
        )
    else:
        scope = (
            "Return a complete revised draft. Preserve every citation token "
            "of the form [src: filename, L<n>] or [src: filename, p<page>, "
            "\"quote\"] from the original draft unless the officer's "
            "instruction explicitly asks to change them. Return only the "
            "revised draft text — no preamble."
        )

    system = (
        "You are revising a draft police report on behalf of a detective. "
        "This is a §13663(b) editing pass, not the first AI draft. "
        "Only state facts present in the case documents listed below or in "
        "the existing draft. Do not invent witnesses, times, or quotes.\n\n"
        f"=== CASE DOCUMENTS ===\n{doc_summary}\n\n"
        f"=== CURRENT DRAFT (revision {len(report.revisions or []) - 1}) ===\n"
        f"{report.final_text}\n=== END CURRENT DRAFT ===\n\n"
        f"{scope}"
    )
    user_prompt = body.instruction

    llm = get_llm_provider()
    response = llm.chat(system=system, user=user_prompt)

    # Record this model as having contributed so the §13663(a)(1) disclosure
    # is honest — even if the officer ends up rejecting the proposal.
    key = (response.provider or "unknown-provider", response.model or "")
    existing = {(p.name, p.version) for p in (report.ai_programs_used or [])}
    if key not in existing:
        report.ai_programs_used.append(AIProgram(
            name=response.provider or "unknown-provider",
            version=response.model or "",
            provider=response.provider or "",
        ))
        report.save()

    case_audit.log_user_event(
        user,
        event_type=AuditEventType.MESSAGE_ASSISTANT,
        case_id=str(report.case.id), report_id=str(report.id),
        summary=f"AI revise proposal ({response.completion_tokens} tokens)",
        detail={
            "instruction": body.instruction[:300],
            "has_selection": bool(body.selected_text),
            "model": response.model,
            "provider": response.provider,
            "purpose": "report_revise_proposal",
        },
    )

    return {
        "proposed_text": response.content,
        "applies_to": "selection" if body.selected_text else "whole_draft",
        "model": response.model,
        "provider": response.provider,
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
    }


@router.post("/{report_id}/sign")
@require_perm("report.sign")
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

    # F19 — signing identity comes from the authenticated session, NOT the
    # body. user.display_name is derived from UserContext; the body can only
    # supply the badge number (recorded next to user_id so the audit log
    # surfaces any mismatch the agency wants to flag).
    now = datetime.utcnow()
    content_hash = hash_text(report.final_text)
    sig = OfficerSignature(
        user_id=user.user_id,
        display_name=user.display_name or user.user_id,
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

    # Surface the action on the case so the dashboard / list views see it.
    if report.case:
        report.case.last_activity_at = now
        report.case.save()

    case_audit.log(
        tenant_id=user.tenant_id, user_id=user.user_id,
        user_display=user.display_name, ip_address=user.ip_address,
        event_type=AuditEventType.REPORT_SIGNED,
        case_id=str(report.case.id), report_id=str(report.id),
        summary=f"Signed report {report.title!r} by {user.display_name or user.user_id}",
        detail={
            "content_sha256": content_hash,
            "authenticated_user_id": user.user_id,
            "authenticated_display_name": user.display_name,
            "claimed_badge_number": body.badge_number,
            "ai_programs": [
                {"name": p.name, "version": p.version, "provider": p.provider}
                for p in report.ai_programs_used
            ],
        },
    )
    return report.to_dict()


@router.post("/{report_id}/export")
@require_perm("report.export")
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
    # F7 — auto-pair the chain-of-custody PDF on every export. Both PDFs
    # travel together so the §13663(c) audit trail is never separated from
    # the §13663(a) signed report.
    chain_path = export_chain_pdf(report)
    report.exported_artifact_uri = f"file://{pdf_path}"
    report.chain_artifact_uri = f"file://{chain_path}"
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
@require_perm("case.read")
def download_report_pdf(report_id: str, user: CurrentUser = Depends(current_user)):
    """Stream the signed-and-exported PDF. Canonical artifact under business rule #14."""
    from providers.document_storage import get_document_storage_provider
    report = Report.objects(id=report_id, tenant_id=user.tenant_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    if not report.exported_artifact_uri:
        raise HTTPException(409, "Report has not been exported yet")
    path = get_document_storage_provider().resolve_path(report.exported_artifact_uri)
    return FileResponse(path, media_type="application/pdf", filename=f"{report.title or report.id}.pdf")


@router.get("/{report_id}/chain.pdf")
@require_perm("case.read")
def download_chain_pdf(report_id: str, user: CurrentUser = Depends(current_user)):
    """F7 — Chain-of-Custody PDF (§13663(c) audit trail).

    Cached forever once written: a signed report is immutable, so the chain
    derived from it cannot change. We regenerate only if the cached file is
    missing on disk (e.g., volume re-created)."""
    from providers.document_storage import get_document_storage_provider
    report = Report.objects(id=report_id, tenant_id=user.tenant_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    if not report.signature:
        raise HTTPException(409, "Report is not yet signed — chain export requires a signed report")
    if report.chain_artifact_uri:
        path = get_document_storage_provider().resolve_path(report.chain_artifact_uri)
        if os.path.exists(path):
            return FileResponse(path, media_type="application/pdf",
                                filename=f"{report.title or report.id}.chain.pdf")
    path = export_chain_pdf(report)
    report.chain_artifact_uri = f"file://{path}"
    report.save()
    return FileResponse(path, media_type="application/pdf",
                        filename=f"{report.title or report.id}.chain.pdf")


@router.get("/{report_id}/diff")
@require_perm("case.read")
def get_report_diff(
    report_id: str,
    against_seq: int | None = None,
    user: CurrentUser = Depends(current_user),
):
    """F9 — Officer's editorial work. JSON diff between the §13663(b) first
    AI draft and the signed text (or any revision via ?against_seq=)."""
    report = Report.objects(id=report_id, tenant_id=user.tenant_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    try:
        return compute_diff(report, against_seq=against_seq)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/{report_id}/diff.pdf")
@require_perm("case.read")
def download_report_diff_pdf(report_id: str, user: CurrentUser = Depends(current_user)):
    """F9 — Officer's editorial work, as a printable PDF."""
    from fastapi.responses import FileResponse as _FR
    report = Report.objects(id=report_id, tenant_id=user.tenant_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    path = export_diff_pdf(report)
    return _FR(path, media_type="application/pdf",
               filename=f"{report.title or report.id}.diff.pdf")


@router.get("/cases/{case_id}/reports")
@require_perm("case.read")
def list_reports_for_case(case_id: str, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    reports = Report.objects(case=case).order_by("-created_at")
    return {"reports": [r.to_dict() for r in reports]}
