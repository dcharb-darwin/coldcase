"""AI-suggested next investigative steps for a case.

Reads what the case actually has — documents, people, reports, refusal
flags, tags, timeline events — and proposes concrete next moves with
rationale. Phase C extension; same accept/dismiss UX as the tag, person,
and timeline-event suggesters. Detective never sees auto-applied steps.

Unlike the existing chat prompt "Suggest next investigative steps", this
endpoint is **state-aware**: it has structured context about every
artifact the case has accumulated, not just the document text. That lets
the model say "follow up with NAACP" because it sees a `Witness` Person
named Hinton on the case, or "request CBI ballistics" because there's a
`forensics`-tagged report with refusal flags.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from models import Case, Document, Person, TagAssignment, TagSubjectKind, TimelineEntry
from models.message import Message
from models.report import Report
from providers.llm import get_llm_provider
from routers._deps import CurrentUser, current_user, require_perm
from services.document_text import extract_text
from services.vendor_scope import enforce_vendor_scope


logger = logging.getLogger(__name__)
_JSON_BLOCK_RE = re.compile(r"\[\s*(?:\{[\s\S]*?\}\s*,?\s*)+\]")


def _extract_json_list(text: str) -> list[dict]:
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


router = APIRouter(
    tags=["Next steps"],
    dependencies=[Depends(enforce_vendor_scope)],
)


# Pre-defined categories give the UI something stable to render with.
# Mirror the design-doc intent: investigative actions are not legal
# advice — they're prompts to the detective, not directives.
_CATEGORIES = (
    "interview",        # talk to a witness / suspect / family
    "evidence",         # request lab work, pull a record, search a location
    "legal",            # confer with DA, draft motion, request order
    "documentation",    # write up, get statement, file a report
    "research",         # background check, prior cases, public records
    "other",
)


@router.post("/cases/{case_id}/next-steps/suggestions")
@require_perm("case.read")
def suggest_next_steps(case_id: str, user: CurrentUser = Depends(current_user)):
    """Generate state-aware investigative-step suggestions for the case."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    # Gather structured state. This is the difference vs the static
    # chat prompt — the model gets the actual current shape of the case
    # so it can build on what's already known.
    docs = list(Document.objects(case=case)[:8])
    snippets: list[str] = []
    for d in docs:
        try:
            text = extract_text(d)
        except Exception:  # noqa: BLE001
            text = ""
        if text:
            snippets.append(f"=== {d.original_filename} ===\n{text[:1800]}")
    docs_block = "\n\n".join(snippets) if snippets else "(no extractable document text)"

    persons = list(Person.objects(tenant_id=user.tenant_id, case=case))
    persons_block = (
        "\n".join(
            f"- {p.name} ({p.role}) — {p.descriptor or 'no descriptor'}"
            for p in persons
        ) if persons else "(no people recorded)"
    )

    reports = list(Report.objects(tenant_id=user.tenant_id, case=case))
    signed = [r for r in reports if r.status in ("signed", "exported")]
    drafts = [r for r in reports if r.status == "draft"]
    reports_block = (
        f"{len(reports)} report(s) total · {len(signed)} signed · {len(drafts)} draft. "
        + ", ".join(f'"{r.title}" ({r.status})' for r in reports[:5])
        if reports else "(no reports yet)"
    )

    # User-applied tags on the case.
    assignments = TagAssignment.objects(
        tenant_id=user.tenant_id,
        subject_kind=TagSubjectKind.CASE.value,
        subject_id=case_id,
    )
    tags_block = ", ".join(sorted({a.tag_id for a in assignments})) if assignments else "(none)"

    # Recent refusal_detected messages signal an extraction problem that
    # may need re-asking or a different doc — worth surfacing to the model.
    refusal_count = 0
    for m in Message.objects(tenant_id=user.tenant_id, role="assistant").only("conversation", "extra"):
        if not getattr(m, "extra", None):
            continue
        if not m.extra.get("refusal_detected"):
            continue
        conv = m.conversation
        if conv and getattr(conv, "case", None) and str(conv.case.id) == case_id:
            refusal_count += 1

    timeline = list(TimelineEntry.objects(tenant_id=user.tenant_id, case=case).order_by("occurred_at"))
    timeline_block = (
        "\n".join(f"- {t.occurred_at}: {t.label}" for t in timeline[:10])
        if timeline else "(no curated timeline events yet)"
    )

    categories = ", ".join(_CATEGORIES)
    system = (
        "Propose concrete next investigative steps for a cold-case "
        "investigator. Return a JSON array of up to 6 objects with: "
        "`step` (one short imperative sentence under 100 chars — what the "
        "detective should do), "
        f"`category` (one of: {categories}), and "
        "`rationale` (one short sentence under 25 words explaining why this "
        "step now, ideally citing a specific case fact: a person, "
        "document, or gap in the record). "
        "These are suggestions, never directives. Don't propose legal "
        "advice. Skip steps that are already done (e.g. don't say 'sign "
        "the report' if signed reports exist). Prefer actions that move "
        "the case forward — interviews to schedule, evidence to request, "
        "records to pull — over abstract guidance. Skip generic admin "
        "(no 'review the case file')."
    )
    user_prompt = (
        f"Case: {case.case_number} — {case.title}\n"
        f"Classification: {case.classification}\n"
        f"Status: {case.status}\n"
        f"Description: {case.description or '(none)'}\n\n"
        f"People on case:\n{persons_block}\n\n"
        f"Reports: {reports_block}\n\n"
        f"Tags applied: {tags_block}\n\n"
        f"Curated timeline:\n{timeline_block}\n\n"
        f"Quality signals: {refusal_count} assistant messages had refusal_detected.\n\n"
        f"Document excerpts:\n{docs_block}\n\n"
        f"Return JSON only."
    )

    try:
        provider = get_llm_provider()
        resp = provider.chat(system=system, user=user_prompt)
        raw = resp.content if hasattr(resp, "content") else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("Next-steps suggestion provider failed: %s", exc)
        return {"suggestions": [], "reason": f"LLM unavailable: {exc}"}

    parsed = _extract_json_list(raw)
    suggestions: list[dict] = []
    seen_steps: set[str] = set()
    for item in parsed:
        if not isinstance(item, dict):
            continue
        step = (item.get("step") or "").strip()
        if not step or step.lower() in seen_steps:
            continue
        category = (item.get("category") or "other").strip().lower()
        if category not in _CATEGORIES:
            category = "other"
        seen_steps.add(step.lower())
        suggestions.append({
            "step": step,
            "category": category,
            "rationale": (item.get("rationale") or "").strip(),
        })
        if len(suggestions) >= 6:
            break

    return {"suggestions": suggestions, "model": getattr(resp, "model", "")}
