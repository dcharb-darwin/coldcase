"""Hypotheses + brain dumps.

Workflow:
1. Detective brain-dumps freely (typed here in Phase 1; voice / upload
   land in Phase 2). The dump persists as a `BrainDump` artifact.
2. POST /cases/{id}/brain-dumps/{id}/suggest-hypotheses — LLM reads the
   transcript + case docs, returns candidate hypotheses with rationale +
   supporting excerpts. Persists nothing.
3. Detective accepts each candidate individually → real `Hypothesis`
   record (status=investigating).
4. POST /cases/{id}/hypotheses/{id}/check — LLM re-reads case docs and
   returns `supporting / contradicting / gap` findings to append to the
   hypothesis's findings list. Detective accepts each finding.
5. PATCH /cases/{id}/hypotheses/{id} — status transitions
   (investigating → confirmed / disproved / superseded), audited.

All AI lineage is preserved: BrainDump → suggested hypothesis → accepted
hypothesis → individual findings. PRA / discovery can trace every
approved investigation back to the original detective utterance.
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
    BrainDump, BrainDumpSource,
    Case, Document,
    Hypothesis, HypothesisStatus, HypothesisFinding, HypothesisFindingKind,
)
from models.audit_event import AuditEventType
from providers.llm import get_llm_provider
from routers._deps import CurrentUser, current_user, require_perm
from services import case_audit
from services.document_text import extract_text
from services.vendor_scope import enforce_vendor_scope


logger = logging.getLogger(__name__)
_JSON_BLOCK_RE = re.compile(r"\[\s*(?:\{[\s\S]*?\}\s*,?\s*)+\]")


router = APIRouter(
    tags=["Hypotheses"],
    dependencies=[Depends(enforce_vendor_scope)],
)


def _extract_json_list(text: str) -> list[dict]:
    if not text:
        return []
    m = _JSON_BLOCK_RE.search(text)
    if not m:
        return []
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _case_docs_block(case: Case, char_limit: int = 2400, max_docs: int = 8) -> tuple[str, dict[str, str]]:
    """Return (joined text block, doc_id → filename map) for prompting."""
    docs = list(Document.objects(case=case)[:max_docs])
    blocks: list[str] = []
    name_by_id: dict[str, str] = {}
    for d in docs:
        try:
            text = extract_text(d)
        except Exception:  # noqa: BLE001
            text = ""
        if not text:
            continue
        did = str(d.id)
        name_by_id[did] = d.original_filename
        blocks.append(f"=== {d.original_filename} (doc_id={did}) ===\n{text[:char_limit]}")
    return "\n\n".join(blocks), name_by_id


# ── Brain dumps ────────────────────────────────────────────────────────────


class CreateBrainDumpBody(BaseModel):
    transcript: str = Field(min_length=1, max_length=40_000)


@router.post("/cases/{case_id}/brain-dumps", status_code=201)
@require_perm("case.edit")
def create_brain_dump(
    case_id: str, body: CreateBrainDumpBody, user: CurrentUser = Depends(current_user),
):
    """Typed brain dump (Phase 1). Voice / upload paths land in Phase 2 and
    will hit a different endpoint that accepts multipart audio + then
    transcribes."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    bd = BrainDump(
        tenant_id=user.tenant_id, case=case,
        source=BrainDumpSource.TYPED.value,
        transcript=body.transcript.strip(),
        created_by=user.user_id,
    ).save()

    case_audit.log_user_event(
        user,
        event_type=AuditEventType.BRAIN_DUMP_CREATED,
        case_id=str(case.id),
        summary=f"Detective brain-dump captured ({len(bd.transcript)} chars, {bd.source})",
        detail={"brain_dump_id": str(bd.id), "source": bd.source},
    )
    return bd.to_dict()


@router.get("/cases/{case_id}/brain-dumps")
@require_perm("case.read")
def list_brain_dumps(case_id: str, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    rows = BrainDump.objects(tenant_id=user.tenant_id, case=case).order_by("-created_at")
    return {"brain_dumps": [r.to_dict() for r in rows]}


# ── Hypothesis suggestion from a brain dump ─────────────────────────────────


@router.post("/cases/{case_id}/brain-dumps/{dump_id}/suggest-hypotheses")
@require_perm("case.read")
def suggest_hypotheses(
    case_id: str, dump_id: str, user: CurrentUser = Depends(current_user),
):
    """LLM reads the brain-dump transcript + case docs and proposes
    structured hypotheses. Persists nothing. Detective accepts each
    individually via the /hypotheses/accept endpoint."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    dump = BrainDump.objects(id=dump_id, tenant_id=user.tenant_id, case=case).first()
    if not dump or not dump.transcript.strip():
        raise HTTPException(404, "Brain dump not found or empty")

    docs_block, _ = _case_docs_block(case)

    system = (
        "Extract distinct investigative hypotheses from a cold-case "
        "detective's unstructured brain-dump. The detective speaks freely; "
        "your job is to hone the dump into structured, falsifiable claims. "
        "For each distinct hypothesis return a JSON object with: "
        "`title` (under 12 words — the claim, not the question), "
        "`body` (1–3 sentences elaborating the claim and what would test it), "
        "`rationale` (one sentence explaining what in the brain-dump or the "
        "case documents prompted this hypothesis). "
        "Return a JSON array, up to 6 entries. Be conservative — only "
        "include hypotheses the detective explicitly raised or that the "
        "documents directly support. Do not invent hypotheses the detective "
        "didn't mention."
    )
    user_prompt = (
        f"Case: {case.case_number} — {case.title}\n"
        f"Classification: {case.classification}\n\n"
        f"=== DETECTIVE BRAIN-DUMP TRANSCRIPT ===\n{dump.transcript}\n\n"
        f"=== CASE DOCUMENTS ===\n{docs_block or '(no extractable text on this case)'}\n\n"
        f"Return JSON only."
    )

    try:
        provider = get_llm_provider()
        resp = provider.chat(system=system, user=user_prompt)
        raw = resp.content if hasattr(resp, "content") else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("Hypothesis suggestion provider failed: %s", exc)
        return {"suggestions": [], "reason": f"LLM unavailable: {exc}"}

    parsed = _extract_json_list(raw)
    suggestions: list[dict] = []
    seen: set[str] = set()
    for item in parsed:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        suggestions.append({
            "title": title,
            "body": (item.get("body") or "").strip(),
            "rationale": (item.get("rationale") or "").strip(),
        })
        if len(suggestions) >= 6:
            break
    return {
        "brain_dump_id": str(dump.id),
        "suggestions": suggestions,
        "model": getattr(resp, "model", ""),
    }


class AcceptHypothesisBody(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(default="", max_length=8000)
    rationale: str = Field(default="", max_length=600)
    brain_dump_id: Optional[str] = None
    model: str = Field(default="", max_length=120)


@router.post("/cases/{case_id}/hypotheses", status_code=201)
@require_perm("case.edit")
def create_hypothesis(
    case_id: str, body: AcceptHypothesisBody, user: CurrentUser = Depends(current_user),
):
    """Accept a suggested hypothesis OR create a manual one. Both paths
    land here; the difference is `brain_dump_id` + `model` populated for
    AI-derived hypotheses."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    bd = None
    if body.brain_dump_id:
        bd = BrainDump.objects(id=body.brain_dump_id, tenant_id=user.tenant_id, case=case).first()
        if not bd:
            raise HTTPException(404, "Brain dump not found on this case")

    now = datetime.utcnow()
    h = Hypothesis(
        tenant_id=user.tenant_id, case=case,
        title=body.title.strip(),
        body=body.body.strip(),
        rationale=body.rationale.strip(),
        status=HypothesisStatus.INVESTIGATING.value,
        brain_dump=bd,
        proposed_by_model=body.model if body.brain_dump_id else "",
        proposed_at=now if body.brain_dump_id else None,
        accepted_by=user.user_id if body.brain_dump_id else "",
        accepted_at=now if body.brain_dump_id else None,
        status_changed_at=now,
        created_by=user.user_id, updated_by=user.user_id,
    ).save()

    case_audit.log_user_event(
        user,
        event_type=AuditEventType.HYPOTHESIS_ACCEPTED_FROM_AI if body.brain_dump_id
            else AuditEventType.HYPOTHESIS_CREATED,
        case_id=str(case.id),
        summary=f"Hypothesis under investigation: '{h.title[:80]}'",
        detail={
            "hypothesis_id": str(h.id),
            "title": h.title,
            "brain_dump_id": str(bd.id) if bd else None,
            "model": body.model,
        },
    )
    return h.to_dict()


@router.get("/cases/{case_id}/hypotheses")
@require_perm("case.read")
def list_hypotheses(case_id: str, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    rows = Hypothesis.objects(tenant_id=user.tenant_id, case=case).order_by("-updated_at")
    return {"hypotheses": [r.to_dict() for r in rows]}


class UpdateHypothesisBody(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    body: Optional[str] = Field(default=None, max_length=8000)
    status: Optional[HypothesisStatus] = None


@router.patch("/cases/{case_id}/hypotheses/{hyp_id}")
@require_perm("case.edit")
def update_hypothesis(
    case_id: str, hyp_id: str, body: UpdateHypothesisBody,
    user: CurrentUser = Depends(current_user),
):
    h = Hypothesis.objects(id=hyp_id, tenant_id=user.tenant_id).first()
    if not h or str(h.case.id) != case_id:
        raise HTTPException(404, "Hypothesis not found")

    status_change: tuple[str, str] | None = None
    if body.title is not None:
        h.title = body.title.strip()
    if body.body is not None:
        h.body = body.body.strip()
    if body.status is not None and body.status.value != h.status:
        status_change = (h.status, body.status.value)
        h.status = body.status.value
        h.status_changed_at = datetime.utcnow()

    h.updated_by = user.user_id
    h.updated_at = datetime.utcnow()
    h.save()

    if status_change:
        case_audit.log_user_event(
            user,
            event_type=AuditEventType.HYPOTHESIS_STATUS_CHANGED,
            case_id=case_id,
            summary=f"Hypothesis '{h.title[:60]}': {status_change[0]} → {status_change[1]}",
            detail={
                "hypothesis_id": str(h.id),
                "from_status": status_change[0],
                "to_status": status_change[1],
            },
        )
    return h.to_dict()


@router.delete("/cases/{case_id}/hypotheses/{hyp_id}", status_code=204)
@require_perm("case.edit")
def delete_hypothesis(
    case_id: str, hyp_id: str, user: CurrentUser = Depends(current_user),
):
    h = Hypothesis.objects(id=hyp_id, tenant_id=user.tenant_id).first()
    if not h or str(h.case.id) != case_id:
        raise HTTPException(404, "Hypothesis not found")
    title_snap = h.title
    h.delete()
    case_audit.log_user_event(
        user,
        event_type=AuditEventType.HYPOTHESIS_STATUS_CHANGED,
        case_id=case_id,
        summary=f"Hypothesis deleted: '{title_snap[:60]}'",
        detail={"hypothesis_id": hyp_id, "to_status": "deleted"},
    )
    return None


# ── Cross-check a hypothesis against case docs ──────────────────────────────


@router.post("/cases/{case_id}/hypotheses/{hyp_id}/check")
@require_perm("case.read")
def check_hypothesis(
    case_id: str, hyp_id: str, user: CurrentUser = Depends(current_user),
):
    """LLM reads the case documents and looks for evidence that supports,
    contradicts, or has a gap relative to the hypothesis. Returns findings
    for the detective to accept individually — accepting appends to the
    hypothesis's `findings` list."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    h = Hypothesis.objects(id=hyp_id, tenant_id=user.tenant_id, case=case).first()
    if not h:
        raise HTTPException(404, "Hypothesis not found")

    docs_block, name_by_id = _case_docs_block(case)
    if not docs_block:
        return {"findings": [], "reason": "No extractable document text on this case."}

    system = (
        "Cross-reference a cold-case investigative hypothesis against the "
        "case documents. For each piece of evidence return a JSON object: "
        "`kind` (one of: supporting | contradicting | gap), "
        "`excerpt` (the exact short quote from the document, under 30 words), "
        "`rationale` (one sentence explaining the link to the hypothesis), "
        "`source_doc_id` (the doc_id from the document marker). "
        "Use `gap` for things the hypothesis implies but the documents "
        "don't confirm or deny. Return a JSON array, up to 10 entries. "
        "Be conservative — better to under-return than fabricate links."
    )
    user_prompt = (
        f"Hypothesis: {h.title}\n"
        f"{h.body}\n\n"
        f"=== CASE DOCUMENTS ===\n{docs_block}\n\n"
        f"Return JSON only."
    )

    try:
        provider = get_llm_provider()
        resp = provider.chat(system=system, user=user_prompt)
        raw = resp.content if hasattr(resp, "content") else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("Hypothesis check provider failed: %s", exc)
        return {"findings": [], "reason": f"LLM unavailable: {exc}"}

    parsed = _extract_json_list(raw)
    valid_kinds = {k.value for k in HypothesisFindingKind}
    findings: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        kind = (item.get("kind") or "").strip().lower()
        if kind not in valid_kinds:
            continue
        excerpt = (item.get("excerpt") or "").strip()
        if not excerpt and kind != HypothesisFindingKind.GAP.value:
            continue
        source_doc_id = (item.get("source_doc_id") or "").strip()
        if source_doc_id and source_doc_id not in name_by_id:
            source_doc_id = ""
        findings.append({
            "kind": kind,
            "excerpt": excerpt,
            "rationale": (item.get("rationale") or "").strip(),
            "source_doc_id": source_doc_id,
            "source_doc_filename": name_by_id.get(source_doc_id, ""),
        })
        if len(findings) >= 10:
            break

    case_audit.log_user_event(
        user,
        event_type=AuditEventType.HYPOTHESIS_CHECKED,
        case_id=case_id,
        summary=f"AI cross-checked hypothesis '{h.title[:60]}' ({len(findings)} findings)",
        detail={
            "hypothesis_id": str(h.id),
            "model": getattr(resp, "model", ""),
            "finding_count": len(findings),
        },
    )

    return {"findings": findings, "model": getattr(resp, "model", "")}


class AcceptFindingBody(BaseModel):
    kind: str = Field(min_length=1, max_length=20)
    excerpt: str = Field(default="", max_length=600)
    rationale: str = Field(default="", max_length=600)
    source_doc_id: str = Field(default="", max_length=64)
    source_doc_filename: str = Field(default="", max_length=300)
    model: str = Field(default="", max_length=120)


@router.post("/cases/{case_id}/hypotheses/{hyp_id}/findings", status_code=201)
@require_perm("case.edit")
def accept_finding(
    case_id: str, hyp_id: str, body: AcceptFindingBody,
    user: CurrentUser = Depends(current_user),
):
    """Accept one finding from a /check response into the hypothesis
    record. Appends to the hypothesis's findings list + audit event."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    h = Hypothesis.objects(id=hyp_id, tenant_id=user.tenant_id, case=case).first()
    if not h:
        raise HTTPException(404, "Hypothesis not found")

    kind = body.kind.strip().lower()
    if kind not in {k.value for k in HypothesisFindingKind}:
        raise HTTPException(422, f"Invalid finding kind {kind!r}")

    now = datetime.utcnow()
    finding = HypothesisFinding(
        kind=kind,
        excerpt=body.excerpt.strip(),
        rationale=body.rationale.strip(),
        source_doc_id=body.source_doc_id,
        source_doc_filename=body.source_doc_filename,
        accepted_by=user.user_id,
        accepted_at=now,
        suggested_by_model=body.model,
    )
    h.findings = list(h.findings or []) + [finding]
    h.updated_by = user.user_id
    h.updated_at = now
    h.save()

    case_audit.log_user_event(
        user,
        event_type=AuditEventType.HYPOTHESIS_FINDING_ACCEPTED,
        case_id=case_id,
        summary=f"Accepted {kind} finding on hypothesis '{h.title[:60]}'",
        detail={
            "hypothesis_id": str(h.id),
            "finding_kind": kind,
            "source_doc_id": body.source_doc_id,
            "model": body.model,
        },
    )
    return h.to_dict()
