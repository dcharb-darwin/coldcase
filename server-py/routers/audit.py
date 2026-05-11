"""F4 — §13663 audit endpoints.

Two views:
  1. Per-report chain — given an approved/signed/exported Report, return the
     full conversation tree that led to it (including discarded drafts) with
     the first AI draft clearly labeled "not an officer statement (§13663(b))".
  2. Range scan — by user / case / date range / event type, for city-attorney
     auditing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from models import Case, Conversation, Message
from models.audit_event import AuditEvent
from models.report import Report
from routers._deps import CurrentUser, current_user


router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/reports/{report_id}/chain")
def report_chain(report_id: str, user: CurrentUser = Depends(current_user)):
    """The full prompt → response chain underpinning a Report. This is the
    artifact a city attorney would request under §13663(c)."""
    report = Report.objects(id=report_id, tenant_id=user.tenant_id).first()
    if not report:
        raise HTTPException(404, "Report not found")

    conv = report.conversation
    messages = list(Message.objects(conversation=conv).order_by("timestamp"))

    chain = []
    for m in messages:
        entry = m.to_dict()
        if m.is_first_ai_draft and str(m.id) == report.first_ai_draft_message_id:
            entry["statutory_note"] = (
                "First AI draft — not an officer statement (California Penal Code §13663(b))."
            )
        chain.append(entry)

    audit_events = list(AuditEvent.objects(report_id=str(report.id)).order_by("timestamp"))

    return {
        "report": report.to_dict(),
        "conversation": conv.to_dict(),
        "case": report.case.to_dict(),
        "chain": chain,
        "audit_events": [e.to_dict() for e in audit_events],
        "statutory_attestation": {
            "penal_code": "California Penal Code §13663",
            "disclosure": report.statutory_disclosure,
            "ai_programs_used": [
                {"name": p.name, "version": p.version, "provider": p.provider}
                for p in (report.ai_programs_used or [])
            ],
        },
    }


@router.get("/events")
def list_events(
    user: CurrentUser = Depends(current_user),
    case_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
):
    """Filter audit events. The tenant scope is always enforced."""
    qs = AuditEvent.objects(tenant_id=user.tenant_id)
    if case_id:
        qs = qs.filter(case_id=case_id)
    if user_id:
        qs = qs.filter(user_id=user_id)
    if event_type:
        qs = qs.filter(event_type=event_type)
    if since:
        qs = qs.filter(timestamp__gte=since)
    if until:
        qs = qs.filter(timestamp__lte=until)
    events = list(qs.order_by("-timestamp").limit(limit))
    return {"events": [e.to_dict() for e in events], "count": len(events)}


@router.get("/cases/{case_id}/summary")
def case_audit_summary(case_id: str, user: CurrentUser = Depends(current_user)):
    """High-level audit summary for a case — counts by event type, list of
    signed reports, list of AI programs ever used in this case."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    events = list(AuditEvent.objects(case_id=str(case.id)))
    counts: dict[str, int] = {}
    for e in events:
        counts[e.event_type] = counts.get(e.event_type, 0) + 1

    reports = list(Report.objects(case=case))
    programs: set[tuple[str, str]] = set()
    for r in reports:
        for p in (r.ai_programs_used or []):
            programs.add((p.name, p.version))

    return {
        "case": case.to_dict(),
        "event_counts": counts,
        "total_events": len(events),
        "reports": [
            {"id": str(r.id), "title": r.title, "status": r.status, "signed_at": r.signed_at.isoformat() if r.signed_at else None}
            for r in reports
        ],
        "distinct_ai_programs": [{"name": n, "version": v} for (n, v) in sorted(programs)],
    }
