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

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from pathlib import PurePosixPath

from models import (
    BrainDump, BrainDumpSource,
    Case, Document,
    Hypothesis, HypothesisStatus, HypothesisOrigin,
    HypothesisFinding, HypothesisFindingKind,
)
from services.bias_vocab import BIAS_FLAGS, BIAS_SLUGS, bias_vocab_for_prompt
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
        "Return a JSON array, up to 6 entries. Stay grounded in the "
        "documents — do not invent claims neither the detective nor the "
        "documents support. BUT: include at least one hypothesis the "
        "detective did NOT raise but the documents directly suggest. The "
        "detective's brain dump may be anchored on one theory; your value "
        "is partly in showing them an angle they haven't said out loud."
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
    # Multi-agent metadata. If omitted, inferred:
    #   brain_dump_id present → ai_from_braindump
    #   parent_hypothesis_id present → ai_alternative
    #   model present but no brain dump → ai_de_novo
    #   otherwise → human_typed
    origin: Optional[HypothesisOrigin] = None
    parent_hypothesis_id: Optional[str] = None


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

    parent_id = (body.parent_hypothesis_id or "").strip()
    if parent_id:
        parent = Hypothesis.objects(id=parent_id, tenant_id=user.tenant_id, case=case).first()
        if not parent:
            raise HTTPException(404, "Parent hypothesis not found on this case")

    # Infer origin from the body's signals if the caller didn't declare one.
    if body.origin is not None:
        origin = body.origin.value
    elif parent_id:
        origin = HypothesisOrigin.AI_ALTERNATIVE.value
    elif body.brain_dump_id:
        origin = HypothesisOrigin.AI_FROM_BRAINDUMP.value
    elif body.model:
        origin = HypothesisOrigin.AI_DE_NOVO.value
    else:
        origin = HypothesisOrigin.HUMAN_TYPED.value

    is_ai = origin != HypothesisOrigin.HUMAN_TYPED.value
    now = datetime.utcnow()
    h = Hypothesis(
        tenant_id=user.tenant_id, case=case,
        title=body.title.strip(),
        body=body.body.strip(),
        rationale=body.rationale.strip(),
        status=HypothesisStatus.INVESTIGATING.value,
        origin=origin,
        parent_hypothesis_id=parent_id,
        brain_dump=bd,
        proposed_by_model=body.model if is_ai else "",
        proposed_at=now if is_ai else None,
        accepted_by=user.user_id if is_ai else "",
        accepted_at=now if is_ai else None,
        status_changed_at=now,
        created_by=user.user_id, updated_by=user.user_id,
    ).save()

    event_type = (
        AuditEventType.HYPOTHESIS_ACCEPTED_FROM_AI if is_ai
        else AuditEventType.HYPOTHESIS_CREATED
    )
    case_audit.log_user_event(
        user,
        event_type=event_type,
        case_id=str(case.id),
        summary=f"Hypothesis under investigation [{origin}]: '{h.title[:80]}'",
        detail={
            "hypothesis_id": str(h.id),
            "title": h.title,
            "origin": origin,
            "parent_hypothesis_id": parent_id,
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


# ── De-novo hypothesis generator (no brain dump) ───────────────────────────
#
# Sibling to suggest-hypotheses but reads case docs without a brain dump
# anchor. Use when the detective is stuck, suspicious of their own framing,
# or onboarding to a case they didn't open. Output is unanchored to any
# detective utterance — gives a "fresh investigator" perspective.


@router.post("/cases/{case_id}/hypotheses/generate")
@require_perm("case.read")
def generate_de_novo_hypotheses(
    case_id: str, user: CurrentUser = Depends(current_user),
):
    """De-novo agent — case documents only, no brain dump. Returns
    candidate hypotheses framed as questions the docs raise but no one
    has answered. Persists nothing; detective accepts each into a
    Hypothesis with origin=ai_de_novo."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    docs_block, _ = _case_docs_block(case)
    if not docs_block:
        return {"suggestions": [], "reason": "No extractable document text on this case."}

    system = (
        "You are a fresh-eyes investigator reading a cold-case file for "
        "the first time. The detective has NOT given you their theory. "
        "Read the documents and propose hypotheses that the documents "
        "themselves raise — questions, contradictions, or unexplained "
        "facts that anyone reviewing the file would notice. "
        "For each hypothesis return a JSON object with: "
        "`title` (under 12 words — the claim, not the question), "
        "`body` (1–3 sentences with what would test it), "
        "`rationale` (one sentence pointing at what in the documents "
        "raised this — quote a phrase if possible). "
        "Return a JSON array, up to 6 entries. Prefer hypotheses that "
        "the existing record does NOT already address. Stay grounded — "
        "do not invent facts not in the documents."
    )
    user_prompt = (
        f"Case: {case.case_number} — {case.title}\n"
        f"Classification: {case.classification}\n\n"
        f"=== CASE DOCUMENTS ===\n{docs_block}\n\n"
        f"Return JSON only."
    )

    try:
        provider = get_llm_provider()
        resp = provider.chat(system=system, user=user_prompt)
        raw = resp.content if hasattr(resp, "content") else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("De-novo hypothesis generator failed: %s", exc)
        return {"suggestions": [], "reason": f"LLM unavailable: {exc}"}

    parsed = _extract_json_list(raw)
    suggestions: list[dict] = []
    seen: set[str] = set()
    for item in parsed:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        suggestions.append({
            "title": title,
            "body": (item.get("body") or "").strip(),
            "rationale": (item.get("rationale") or "").strip(),
        })
        if len(suggestions) >= 6:
            break

    case_audit.log_user_event(
        user,
        event_type=AuditEventType.HYPOTHESIS_GENERATED_DE_NOVO,
        case_id=str(case.id),
        summary=f"De-novo hypothesis generator surfaced {len(suggestions)} candidate(s)",
        detail={
            "model": getattr(resp, "model", ""),
            "candidate_count": len(suggestions),
        },
    )

    return {"suggestions": suggestions, "model": getattr(resp, "model", "")}


# ── Red-team: challenge a specific hypothesis ──────────────────────────────


@router.post("/cases/{case_id}/hypotheses/{hyp_id}/red-team")
@require_perm("case.edit")  # mutates bias_flags + logical_gaps on the hypothesis
def red_team_hypothesis(
    case_id: str, hyp_id: str, user: CurrentUser = Depends(current_user),
):
    """Critic agent — given ONE hypothesis, finds counter-evidence in the
    case documents, proposes alternative explanations that fit the same
    evidence, names cognitive biases the hypothesis may reflect, and
    identifies logical gaps. Counter-evidence + alternatives are
    transient (detective accepts them via the existing endpoints).
    Bias flags + logical gaps persist on the hypothesis itself —
    they belong in the permanent record.
    """
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    target = Hypothesis.objects(id=hyp_id, tenant_id=user.tenant_id, case=case).first()
    if not target:
        raise HTTPException(404, "Hypothesis not found")

    docs_block, name_by_id = _case_docs_block(case)
    siblings = [
        h for h in Hypothesis.objects(tenant_id=user.tenant_id, case=case)
        if str(h.id) != str(target.id)
    ]
    siblings_block = "\n".join(
        f"- [{h.status}] {h.title}" for h in siblings[:8]
    ) or "(no other hypotheses on this case)"

    system = (
        "You are a red-team investigator. Your job is to ATTACK the "
        "given hypothesis — find what's wrong with it. Do not look for "
        "supporting evidence; another agent does that. Do not propose "
        "stronger versions of the claim; that's the wrong direction. "
        "If you cannot find anything that argues against the hypothesis, "
        "return empty arrays — do NOT invent strawmen to look productive.\n"
        "\n"
        "Return a JSON object with four arrays:\n"
        "  counter_evidence: items where the case documents directly "
        "contradict or undermine the hypothesis. Each item: "
        "{excerpt (exact quote, under 30 words), rationale (one sentence "
        "explaining how it contradicts the hypothesis), source_doc_id "
        "(the doc_id from the document marker)}.\n"
        "  alternatives: distinct alternative hypotheses that fit the "
        "SAME evidence equally well. Each: {title (under 12 words), body "
        "(1–2 sentences), rationale (why this fits the same evidence)}.\n"
        "  bias_flags: cognitive biases the hypothesis MAY reflect. "
        "Choose ONLY from this closed vocabulary (return the slug):\n"
        f"{bias_vocab_for_prompt()}\n"
        "  logical_gaps: strings naming what the hypothesis assumes but "
        "does not establish. One assumption per string.\n"
        "\n"
        "Be calibrated. Empty arrays are valid and preferable to fabrication."
    )
    user_prompt = (
        f"Case: {case.case_number} — {case.title}\n"
        f"Classification: {case.classification}\n\n"
        f"=== HYPOTHESIS UNDER REVIEW ===\n"
        f"Title: {target.title}\n"
        f"Body:  {target.body}\n"
        f"Rationale: {target.rationale}\n"
        f"Status: {target.status}\n"
        f"Origin: {target.origin}\n\n"
        f"=== OTHER HYPOTHESES ON THIS CASE ===\n{siblings_block}\n\n"
        f"=== CASE DOCUMENTS ===\n{docs_block or '(no extractable text on this case)'}\n\n"
        f"Return JSON only — a single object, not an array."
    )

    try:
        provider = get_llm_provider()
        resp = provider.chat(system=system, user=user_prompt)
        raw = resp.content if hasattr(resp, "content") else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("Red-team agent failed: %s", exc)
        return {
            "counter_evidence": [], "alternatives": [],
            "bias_flags": [], "logical_gaps": [],
            "reason": f"LLM unavailable: {exc}",
        }

    # Parse a single JSON object (not array — different shape than other
    # endpoints).
    import re as _re_local
    obj_match = _re_local.search(r"\{[\s\S]*\}", raw)
    parsed: dict = {}
    if obj_match:
        try:
            candidate = json.loads(obj_match.group(0))
            if isinstance(candidate, dict):
                parsed = candidate
        except json.JSONDecodeError:
            pass

    counter_evidence: list[dict] = []
    for item in (parsed.get("counter_evidence") or []):
        if not isinstance(item, dict):
            continue
        excerpt = (item.get("excerpt") or "").strip()
        if not excerpt:
            continue
        source_doc_id = (item.get("source_doc_id") or "").strip()
        if source_doc_id and source_doc_id not in name_by_id:
            source_doc_id = ""
        counter_evidence.append({
            "kind": HypothesisFindingKind.CONTRADICTING.value,
            "excerpt": excerpt,
            "rationale": (item.get("rationale") or "").strip(),
            "source_doc_id": source_doc_id,
            "source_doc_filename": name_by_id.get(source_doc_id, ""),
        })
        if len(counter_evidence) >= 5:
            break

    alternatives: list[dict] = []
    seen_titles: set[str] = set()
    for item in (parsed.get("alternatives") or []):
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        if not title or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())
        alternatives.append({
            "title": title,
            "body": (item.get("body") or "").strip(),
            "rationale": (item.get("rationale") or "").strip(),
        })
        if len(alternatives) >= 5:
            break

    raw_flags = parsed.get("bias_flags") or []
    new_flags = [
        slug for slug in raw_flags
        if isinstance(slug, str) and slug in BIAS_SLUGS
    ]
    raw_gaps = parsed.get("logical_gaps") or []
    new_gaps = [
        (g or "").strip() for g in raw_gaps
        if isinstance(g, str) and (g or "").strip()
    ]

    # Persist bias flags + logical gaps on the hypothesis — they belong
    # in the record. Dedupe against what's already there.
    existing_flags = set(target.bias_flags or [])
    merged_flags = sorted(existing_flags | set(new_flags))
    existing_gaps = list(target.logical_gaps or [])
    merged_gaps = list(existing_gaps)
    for g in new_gaps:
        if g not in merged_gaps:
            merged_gaps.append(g)

    target.bias_flags = merged_flags
    target.logical_gaps = merged_gaps
    target.red_team_count = int(target.red_team_count or 0) + 1
    target.updated_at = datetime.utcnow()
    target.updated_by = user.user_id
    target.save()

    case_audit.log_user_event(
        user,
        event_type=AuditEventType.HYPOTHESIS_RED_TEAMED,
        case_id=str(case.id),
        summary=(
            f"Red-team challenged hypothesis '{target.title[:60]}' — "
            f"{len(counter_evidence)} counter / {len(alternatives)} alt / "
            f"{len(new_flags)} bias / {len(new_gaps)} gap"
        ),
        detail={
            "hypothesis_id": str(target.id),
            "model": getattr(resp, "model", ""),
            "counter_evidence_count": len(counter_evidence),
            "alternative_count": len(alternatives),
            "bias_flags_added": new_flags,
            "logical_gaps_added": new_gaps,
        },
    )

    return {
        "counter_evidence": counter_evidence,
        "alternatives": alternatives,
        "bias_flags": new_flags,
        "logical_gaps": new_gaps,
        "model": getattr(resp, "model", ""),
        "hypothesis": target.to_dict(),
    }


@router.get("/hypothesis-bias-vocab")
def hypothesis_bias_vocab():
    """Public — UI fetches once to render bias-flag chips with tooltips."""
    return {"flags": BIAS_FLAGS}


# ── Audio brain dump: in-portal capture + drag-drop upload ──────────────────


_AUDIO_MIME_PREFIXES = ("audio/",)
_AUDIO_EXTS = {".webm", ".mp3", ".wav", ".m4a", ".ogg", ".oga", ".mp4", ".aac", ".flac"}
_MAX_AUDIO_BYTES = 50 * 1024 * 1024  # 50 MB — long voice memo, conservative


@router.post("/cases/{case_id}/brain-dumps/audio", status_code=201)
@require_perm("case.edit")
def upload_audio_brain_dump(
    case_id: str,
    file: UploadFile = File(...),
    source: str = "audio_uploaded",
    user: CurrentUser = Depends(current_user),
):
    """Multipart audio upload (in-portal MediaRecorder OR drag-drop file).

    Stores raw audio through the artifact_store seam (same one Documents
    use), runs the configured transcription provider, persists a BrainDump
    with the transcript filled in. Detective then reviews + edits the
    transcript before running suggest-hypotheses on it.

    `source` declares whether this came from MediaRecorder (audio_recorded)
    or a file drop (audio_uploaded). Both land in the same model.
    """
    from lib.hash import sha256_bytes
    from services.artifact_store import get_artifact_store
    from providers.transcription import get_transcriber

    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    if source not in {BrainDumpSource.AUDIO_RECORDED.value, BrainDumpSource.AUDIO_UPLOADED.value}:
        raise HTTPException(422, f"Invalid audio source {source!r}")

    data = file.file.read(_MAX_AUDIO_BYTES + 1)
    if len(data) > _MAX_AUDIO_BYTES:
        raise HTTPException(413, f"Audio exceeds {_MAX_AUDIO_BYTES} bytes")
    if not data:
        raise HTTPException(422, "Empty upload")

    mime = file.content_type or "application/octet-stream"
    safe_name = PurePosixPath(file.filename or "brain-dump.webm").name
    if not (mime.startswith(_AUDIO_MIME_PREFIXES) or
            PurePosixPath(safe_name).suffix.lower() in _AUDIO_EXTS):
        raise HTTPException(415, f"Unsupported audio type: mime={mime} name={safe_name}")

    sha = sha256_bytes(data)
    stored = get_artifact_store().put(
        f"brain-dumps/{case.id}/{sha}-{safe_name}", data, content_type=mime,
    )

    transcript = ""
    transcript_model = ""
    transcription_error = ""
    try:
        transcriber = get_transcriber()
        result = transcriber.transcribe(data, mime, safe_name)
        transcript = (result.text or "").strip()
        transcript_model = result.model
    except Exception as exc:  # noqa: BLE001
        logger.warning("Audio transcription failed: %s", exc)
        transcription_error = str(exc)

    bd = BrainDump(
        tenant_id=user.tenant_id, case=case,
        source=source,
        audio_artifact_uri=stored.uri,
        audio_filename=safe_name,
        audio_mime_type=mime,
        transcript=transcript,
        transcript_model=transcript_model,
        created_by=user.user_id,
    ).save()

    case_audit.log_user_event(
        user,
        event_type=AuditEventType.BRAIN_DUMP_CREATED,
        case_id=str(case.id),
        summary=f"Audio brain-dump captured ({source}, {safe_name}, {len(data)} bytes)",
        detail={
            "brain_dump_id": str(bd.id),
            "source": source,
            "audio_filename": safe_name,
            "audio_mime_type": mime,
            "audio_bytes": len(data),
        },
    )
    if transcript:
        case_audit.log_user_event(
            user,
            event_type=AuditEventType.BRAIN_DUMP_TRANSCRIBED,
            case_id=str(case.id),
            summary=f"Audio brain-dump transcribed ({transcript_model}, {len(transcript)} chars)",
            detail={
                "brain_dump_id": str(bd.id),
                "transcript_model": transcript_model,
                "transcript_chars": len(transcript),
            },
        )

    out = bd.to_dict()
    if transcription_error:
        out["transcription_error"] = transcription_error
    return out


class UpdateBrainDumpBody(BaseModel):
    transcript: str = Field(min_length=1, max_length=40_000)


@router.patch("/cases/{case_id}/brain-dumps/{dump_id}")
@require_perm("case.edit")
def update_brain_dump(
    case_id: str, dump_id: str, body: UpdateBrainDumpBody,
    user: CurrentUser = Depends(current_user),
):
    """Edit the transcript — the detective corrects proper nouns, badge
    numbers, dates that Whisper missed. Audio + lineage stay intact."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    bd = BrainDump.objects(id=dump_id, tenant_id=user.tenant_id, case=case).first()
    if not bd:
        raise HTTPException(404, "Brain dump not found on this case")
    bd.transcript = body.transcript.strip()
    bd.updated_at = datetime.utcnow()
    bd.save()
    return bd.to_dict()
