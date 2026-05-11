"""Prompt suggestions surface.

The detective interview surfaced six recurring AI tasks (transcript lines 67-82,
99-105):
  1. Summarize a patrol report.
  2. Build a timeline (for the DA).
  3. Review the detective's own report for gaps.
  4. Generate follow-up interview questions.
  5. Look up applicable Penal Code / CalCrim sections.
  6. Cross-document analysis (deferred — flagged as stretch).

We expose them as a static catalog and (when documents are in context) a
templated form that drops the document filename into the prompt so the
detective can fire it with one click. The actual prompts run through the
ordinary chat path so they land in the §13663 audit trail like any other.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from models import Case, Document
from routers._deps import CurrentUser, current_user


router = APIRouter(prefix="/prompts", tags=["Prompts"])


# Each suggestion has a stable id, a short label for the chip, a short
# explanation surfaced in a tooltip, and a `template` with `{doc}` / `{docs}`
# placeholders. If the template needs no document, omit placeholders.
SUGGESTIONS = [
    {
        "id": "summarize",
        "label": "📝 Summarize",
        "category": "summary",
        "description": "Produce a concise bullet-point summary of the selected document(s).",
        "template": (
            "Summarize the document titled \"{doc}\" in 5 to 8 factual bullet "
            "points suitable for sharing with a supervising sergeant. Only "
            "include facts present in the document; mark anything inferred "
            "as [inferred]. Do not include exculpatory speculation."
        ),
        "needs_document": True,
    },
    {
        "id": "timeline",
        "label": "🕐 Build timeline for DA",
        "category": "timeline",
        "description": "Construct a chronological timeline suitable for the DA's case file from the selected documents.",
        "template": (
            "Using only the documents in context ({docs}), construct a clear "
            "chronological timeline of events relevant to this homicide "
            "investigation. Format each entry as `YYYY-MM-DD HH:MM — event "
            "(source: <document name>)`. When a time is approximate or "
            "inferred, mark it (~) and cite the source language."
        ),
        "needs_document": True,
    },
    {
        "id": "gaps",
        "label": "🔍 Identify gaps in report",
        "category": "review",
        "description": "Review the selected report for gaps, ambiguities, and missing elements a defense attorney could exploit.",
        "template": (
            "Review the document titled \"{doc}\" as a defense attorney would. "
            "Identify gaps, ambiguities, unanswered questions, and any "
            "missing investigative steps. For each issue, cite the specific "
            "language in the report. Do not invent facts."
        ),
        "needs_document": True,
    },
    {
        "id": "interview_qs",
        "label": "❓ Follow-up interview questions",
        "category": "interview",
        "description": "Generate follow-up questions for a witness based on inconsistencies or gaps in their statement.",
        "template": (
            "Based on the witness statement in \"{doc}\" and any other "
            "documents in context, generate 8 to 12 follow-up interview "
            "questions designed to clarify timeline ambiguities, resolve "
            "inconsistencies, and probe for additional details about the "
            "unidentified male described. Group questions by topic."
        ),
        "needs_document": True,
    },
    {
        "id": "penal_code",
        "label": "⚖️ Penal Code / CalCrim check",
        "category": "legal",
        "description": "Identify applicable California Penal Code sections and CalCrim instructions based on the facts.",
        "template": (
            "Based on the facts established in the documents in context "
            "({docs}), identify the California Penal Code section(s) that "
            "appear to apply and the CalCrim jury instruction number(s) "
            "that would govern. For each, state the elements and which "
            "facts in the documents support each element. If an element is "
            "not yet supported by the record, say so."
        ),
        "needs_document": True,
    },
    {
        "id": "inconsistencies",
        "label": "⚠ Inconsistencies between statements",
        "category": "review",
        "description": "Surface contradictions or tensions across multiple documents.",
        "template": (
            "Compare the documents in context ({docs}) and surface any "
            "factual inconsistencies, contradictions, or unresolved tensions "
            "between them. Quote the exact passages and identify each "
            "source. Do not assume motive; just identify the conflict."
        ),
        "needs_document": True,
    },
    {
        "id": "what_next",
        "label": "🎯 Suggest next investigative steps",
        "category": "planning",
        "description": "Suggest the next investigative actions a cold-case detective should take given the current record.",
        "template": (
            "Given the current state of the documents in context, suggest a "
            "prioritized list of the next 5 to 7 investigative steps a "
            "cold-case detective should consider, with the rationale for "
            "each. Be specific to the facts; do not produce a generic checklist."
        ),
        "needs_document": False,
    },
]


@router.get("/suggestions")
def list_suggestions(
    user: CurrentUser = Depends(current_user),
    case_id: Optional[str] = Query(None, description="Case ID — if provided, return templates rendered against the case's documents."),
    document_id: Optional[str] = Query(None, description="If provided, render `{doc}` against this document."),
):
    """Return the suggestion catalog. If `case_id` and (optionally) `document_id`
    are provided, render the templates with concrete filenames so the
    frontend can drop a ready-to-send prompt into the composer.
    """
    rendered: list[dict] = []
    doc_label: str | None = None
    docs_label: str | None = None

    if case_id:
        case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
        if case:
            docs = list(Document.objects(case=case).only("id", "original_filename"))
            docs_label = ", ".join(d.original_filename for d in docs) or "(no documents registered)"
            if document_id:
                target = next((d for d in docs if str(d.id) == document_id), None)
                if target:
                    doc_label = target.original_filename
            if not doc_label and docs:
                doc_label = docs[0].original_filename

    for s in SUGGESTIONS:
        prompt = s["template"]
        if "{doc}" in prompt:
            prompt = prompt.replace("{doc}", doc_label or "(select a document first)")
        if "{docs}" in prompt:
            prompt = prompt.replace("{docs}", docs_label or "(no documents in context)")
        rendered.append({
            "id": s["id"],
            "label": s["label"],
            "category": s["category"],
            "description": s["description"],
            "needs_document": s["needs_document"],
            "rendered_prompt": prompt,
        })

    return {
        "suggestions": rendered,
        "context": {
            "case_id": case_id,
            "document_id": document_id,
            "active_document_label": doc_label,
            "all_documents_label": docs_label,
        },
    }
