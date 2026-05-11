"""F2 — Chat with case (AI proxy + lineage)."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models import (
    Case, Conversation, Message, MessageRole, Document, MediaInput,
)
from models.audit_event import AuditEventType
from providers.llm import AttachedFile, get_llm_provider
from routers._deps import CurrentUser, current_user
from services import case_audit
from services.document_text import extract_text, number_lines


router = APIRouter(tags=["Conversations"])


# ── Bodies ──────────────────────────────────────────────────────────────────


class StartConversationBody(BaseModel):
    title: str = ""


class SendMessageBody(BaseModel):
    content: str = Field(min_length=1)
    parent_message_id: Optional[str] = None
    # Caller declares which documents / media are "in context" for this prompt
    # so the audit trail can answer §13663(c)(2).
    in_context_document_ids: list[str] = Field(default_factory=list)
    in_context_media_ids: list[str] = Field(default_factory=list)


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/cases/{case_id}/conversations", status_code=201)
def start_conversation(case_id: str, body: StartConversationBody, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    conv = Conversation(
        tenant_id=user.tenant_id, case=case, user_id=user.user_id,
        title=body.title or f"Conversation {datetime.utcnow().isoformat(timespec='minutes')}",
    ).save()
    case_audit.log(
        tenant_id=user.tenant_id, user_id=user.user_id,
        user_display=user.display_name, ip_address=user.ip_address,
        event_type=AuditEventType.CONVERSATION_STARTED,
        case_id=str(case.id), conversation_id=str(conv.id),
        summary=f"Started conversation on case {case.case_number}",
    )
    return conv.to_dict()


@router.get("/cases/{case_id}/conversations")
def list_conversations(case_id: str, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    convs = Conversation.objects(case=case).order_by("-last_message_at")
    return {"conversations": [c.to_dict() for c in convs]}


@router.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: str, user: CurrentUser = Depends(current_user)):
    conv = Conversation.objects(id=conversation_id, tenant_id=user.tenant_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    msgs = Message.objects(conversation=conv).order_by("timestamp")
    return {
        "conversation": conv.to_dict(),
        "messages": [m.to_dict() for m in msgs],
    }


# Phrases that indicate the LLM hedged about document access despite our
# having injected the document text into its context. Tripping any of these
# while documents WERE provided flips `extra.refusal_detected` on the message
# so the UI can surface a warning and we have an audit trail.
_REFUSAL_PHRASES: tuple[str, ...] = (
    "do not have access",
    "don't have access",
    "no access to the content",
    "cannot directly quote",
    "cannot quote specific",
    "do not have extractable",
    "no extractable content",
    "please provide the document",
    "please share the relevant",
    "if you can provide",
    "if you could provide",
    "i am unable to access",
    "i'm unable to access",
)


def _detect_refusal(content: str) -> bool:
    lo = (content or "").lower()
    return any(p in lo for p in _REFUSAL_PHRASES)


CITATION_INSTRUCTIONS_INLINE_TEXT = """\
=== DOCUMENT ACCESS — READ THIS BEFORE RESPONDING ===

The documents listed below appear between `--- BEGIN DOCUMENT: <filename> ---`
and `--- END DOCUMENT: <filename> ---` markers. **If a document appears
between those markers, you HAVE that document's contents and you must analyze
it.** You may not respond with phrases like "I do not have access," "I cannot
directly quote," "no extractable content," or "please provide the documents"
for any document that appears below — that is factually incorrect and breaks
the §13663 audit trail.

Some documents are OCR'd from scans and may contain artifacts (misspellings,
spacing oddities, partial words). Work with the legible portions. If a passage
is too garbled to interpret, say "the OCR at [src: <file>, L<n>] is illegible"
— but do this only for specific passages, not as a blanket refusal.

=== CITATION REQUIREMENTS — MANDATORY ===

Every factual claim in your response MUST be followed by a citation token of
the EXACT form:

  [src: <filename>, L<line>]

- <filename> must match exactly one of the document filenames listed below.
- L<line> must reference a line number that appears as [L<n>] in the document text.
- Cite the most specific line that supports the claim.
- Multiple citations allowed, space-separated.
- DO NOT cite media inputs.
- DO NOT invent line numbers. If you can't find a supporting line, say so
  and emit no citation for that claim.

Inferences vs facts: prefix inferred statements with "[inferred] " and emit
no citation for them.
"""


CITATION_INSTRUCTIONS_MULTIMODAL = """\
=== DOCUMENT ACCESS — YOU HAVE THE FILES ATTACHED ===

The PDF files attached to this message are the primary source of fact. Read
them directly — including scanned pages, the model sees image content
natively. You may not respond with phrases like "I do not have access,"
"no extractable content," or "please provide the documents" — the files
are attached.

=== CITATION REQUIREMENTS — MANDATORY ===

Every factual claim in your response MUST be followed by a citation token of
the EXACT form:

  [src: <filename>, p<page>, "<short verbatim quote from the page>"]

- <filename> matches exactly one of the attached files' filenames.
- <page> is the 1-indexed page number where the supporting text appears.
- The quote must be a SHORT verbatim fragment (5-15 words) copied exactly
  as it appears on that page. The quote is what an auditor will search for
  in the source PDF to verify your claim — paraphrases break verification.
- Multiple citations allowed, space-separated.
- DO NOT invent page numbers or quotes. If you can't find a supporting
  passage, say so and emit no citation for that claim.

Examples of correctly-cited factual claims:

  - Body discovered at Riverside Park north boat launch at 06:18 hrs
    [src: patrol-report.pdf, p1, "At 06:18 hrs on 04/12/1992 dispatch received"]
  - Cause of death was blunt-force trauma to the occipital skull
    [src: me-preliminary.pdf, p1, "blunt-force trauma to the posterior cranium"]

Inferences vs facts: prefix inferred statements with "[inferred] " and emit
no citation for them.
"""


# Default to the inline-text instructions; conversations router swaps to the
# multimodal variant when the active LLM provider supports attachments AND
# COLDCASE_LLM_MULTIMODAL is enabled.
CITATION_INSTRUCTIONS = CITATION_INSTRUCTIONS_INLINE_TEXT


_MULTIMODAL_ENABLED = os.environ.get("COLDCASE_LLM_MULTIMODAL", "false").lower() in ("1", "true", "yes")


def _build_attachments(documents: list[Document]) -> list[AttachedFile]:
    """Read each Document's bytes from the storage provider and wrap as an
    AttachedFile. Bytes live only for the request's stack frame — never
    persisted by Cold Case (PRD business rule #17, data residency)."""
    from providers.document_storage import get_document_storage_provider
    storage = get_document_storage_provider()
    out: list[AttachedFile] = []
    for d in documents:
        path = storage.resolve_path(d.storage_uri)
        with open(path, "rb") as f:
            data = f.read()
        out.append(AttachedFile(
            filename=d.original_filename,
            mime_type=d.mime_type or "application/pdf",
            data=data,
        ))
    return out


def _build_system_prompt(
    case: Case,
    documents_in_context: list[Document],
    media_in_context: list[MediaInput],
    *,
    multimodal: bool,
) -> str:
    parts = [
        "You are an AI assistant supporting a law enforcement detective on a cold case.",
        f"Case number: {case.case_number}. Title: {case.title}. Classification: {case.classification}.",
        "Your output may become part of an official report under California Penal Code §13663.",
        "Be factual and rely strictly on the documents provided.",
        "If information is missing or ambiguous, say so plainly — do not speculate.",
    ]
    if documents_in_context:
        parts.append("")
        if multimodal:
            parts.append(CITATION_INSTRUCTIONS_MULTIMODAL)
            parts.append("=== ATTACHED FILES ===")
            for d in documents_in_context:
                parts.append(f"- {d.original_filename} (sha256={d.sha256[:12]}…) — attached above as a PDF")
        else:
            parts.append(CITATION_INSTRUCTIONS_INLINE_TEXT)
            parts.append("=== DOCUMENTS IN CONTEXT (with [L<n>] line anchors) ===")
            for d in documents_in_context:
                text = extract_text(d)
                numbered = number_lines(text) if text else "[document text could not be extracted — only the filename is known]"
                parts.append("")
                parts.append(f"--- BEGIN DOCUMENT: {d.original_filename} (sha256={d.sha256[:12]}…) ---")
                parts.append(numbered)
                parts.append(f"--- END DOCUMENT: {d.original_filename} ---")
    if media_in_context:
        parts.append("")
        parts.append("=== MEDIA INPUTS REFERENCED (not transcribed in this pass) ===")
        for m in media_in_context:
            parts.append(f"- {m.source_type} (sha256={m.sha256[:12]}…, duration={m.duration_seconds}s)"
                         f" — {m.description or 'no description'}")
        parts.append("Do not cite media inputs — their contents are NOT available to you here.")
    return "\n".join(parts)


@router.post("/conversations/{conversation_id}/messages", status_code=201)
def send_message(conversation_id: str, body: SendMessageBody, user: CurrentUser = Depends(current_user)):
    conv = Conversation.objects(id=conversation_id, tenant_id=user.tenant_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    case = conv.case  # ReferenceField is resolved on access

    # Resolve in-context documents / media for the system prompt + lineage.
    # If the caller didn't specify documents, default to ALL documents on the
    # case — a detective asking about THIS case expects the AI to know about
    # the case's documents without manual toggling. The audit log records
    # `implicit_document_context=true` so §13663(c) reflects the actual scope.
    implicit_document_context = not body.in_context_document_ids
    if implicit_document_context:
        documents = list(Document.objects(case=case))
    else:
        documents = list(Document.objects(id__in=body.in_context_document_ids, case=case))
    # Media stays explicit — body cam / interview audio is heavy and rarely
    # desired by default.
    media = list(MediaInput.objects(
        id__in=body.in_context_media_ids, case=case,
    )) if body.in_context_media_ids else []

    # Persist user message (append-only).
    user_msg = Message(
        tenant_id=user.tenant_id, conversation=conv,
        role=MessageRole.USER.value, content=body.content,
        parent_message_id=body.parent_message_id,
        user_id=user.user_id,
        in_context_document_ids=[str(d.id) for d in documents],
        in_context_media_ids=[str(m.id) for m in media],
        extra={"implicit_document_context": implicit_document_context},
    ).save()
    case_audit.log(
        tenant_id=user.tenant_id, user_id=user.user_id,
        user_display=user.display_name, ip_address=user.ip_address,
        event_type=AuditEventType.MESSAGE_USER,
        case_id=str(case.id), conversation_id=str(conv.id), message_id=str(user_msg.id),
        summary=body.content[:160],
        detail={
            "in_context_document_ids": user_msg.in_context_document_ids,
            "in_context_media_ids": user_msg.in_context_media_ids,
            "implicit_document_context": implicit_document_context,
        },
    )

    # Call the LLM. When the provider supports attachments AND the
    # COLDCASE_LLM_MULTIMODAL flag is set, we stream the PDF bytes inline
    # for this single request — never cached, never persisted. (PRD §17)
    llm = get_llm_provider()
    use_multimodal = _MULTIMODAL_ENABLED and getattr(llm, "supports_attachments", False) and bool(documents)
    attachments: list[AttachedFile] | None = None
    if use_multimodal:
        attachments = _build_attachments(documents)
    system_prompt = _build_system_prompt(case, documents, media, multimodal=use_multimodal)
    response = llm.chat(system=system_prompt, user=body.content, attachments=attachments)
    # Bytes go out of scope here — no Cold Case-side persistence.
    attachments = None  # noqa: F841
    refusal_detected = _detect_refusal(response.content) if documents else False

    # Persist assistant response.
    assistant_extra = dict(response.extra or {})
    if refusal_detected:
        assistant_extra["refusal_detected"] = True
    assistant_msg = Message(
        tenant_id=user.tenant_id, conversation=conv,
        role=MessageRole.ASSISTANT.value, content=response.content,
        parent_message_id=str(user_msg.id),
        user_id=user.user_id,
        in_context_document_ids=[str(d.id) for d in documents],
        in_context_media_ids=[str(m.id) for m in media],
        model=response.model, provider=response.provider,
        prompt_tokens=response.prompt_tokens, completion_tokens=response.completion_tokens,
        extra=assistant_extra,
    ).save()
    case_audit.log(
        tenant_id=user.tenant_id, user_id=user.user_id,
        user_display=user.display_name, ip_address=user.ip_address,
        event_type=AuditEventType.MESSAGE_ASSISTANT,
        case_id=str(case.id), conversation_id=str(conv.id), message_id=str(assistant_msg.id),
        summary=f"{response.provider}:{response.model} responded ({response.completion_tokens} tokens)",
        detail={
            "model": response.model,
            "provider": response.provider,
            "refusal_detected": refusal_detected,
        },
    )

    conv.last_message_at = datetime.utcnow()
    conv.save()
    case.last_activity_at = datetime.utcnow()
    case.save()

    return {"user_message": user_msg.to_dict(), "assistant_message": assistant_msg.to_dict()}
