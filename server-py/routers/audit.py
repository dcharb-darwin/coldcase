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
from models.report import Report, ReportStatus
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


@router.get("/anomalies")
def anomalies_report(
    user: CurrentUser = Depends(current_user),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
):
    """F17 — Refusal & Anomaly Report. Two streams the city auditor or
    internal QA wants to see surfaced as actionable signal rather than
    buried in the audit feed:
      - assistant messages where the model hedged about document access
        despite documents being supplied (refusal_detected=true)
      - vendor.access events from the F10 Vendor Access Portal
    """
    # Refusals — look for the flag in the audit event detail, then enrich
    # from the underlying Message for display.
    event_q = AuditEvent.objects(
        tenant_id=user.tenant_id,
        event_type="message.assistant",
    )
    if since:
        event_q = event_q.filter(timestamp__gte=since)
    if until:
        event_q = event_q.filter(timestamp__lte=until)

    refusal_rows: list[dict] = []
    for e in event_q.order_by("-timestamp").limit(limit * 4):
        if not (e.detail or {}).get("refusal_detected"):
            continue
        msg = Message.objects(id=e.message_id).first() if e.message_id else None
        refusal_rows.append({
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "case_id": e.case_id,
            "conversation_id": e.conversation_id,
            "message_id": e.message_id,
            "user_display": e.user_display or e.user_id,
            "model": (e.detail or {}).get("model"),
            "provider": (e.detail or {}).get("provider"),
            "prompt_tokens": msg.prompt_tokens if msg else None,
            "completion_tokens": msg.completion_tokens if msg else None,
            "snippet": (msg.content[:200] if msg and msg.content else None),
        })
        if len(refusal_rows) >= limit:
            break

    # Vendor accesses — pull every VENDOR_ACCESS_* event for the tenant.
    vendor_q = AuditEvent.objects(
        tenant_id=user.tenant_id,
        event_type__startswith="vendor.access",
    )
    if since:
        vendor_q = vendor_q.filter(timestamp__gte=since)
    if until:
        vendor_q = vendor_q.filter(timestamp__lte=until)

    vendor_rows = [
        {
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "event_type": e.event_type,
            "operator": e.user_display or e.user_id,
            "case_id": e.case_id,
            "summary": e.summary,
            "detail": dict(e.detail or {}),
        }
        for e in vendor_q.order_by("-timestamp").limit(limit)
    ]

    return {
        "filter": {
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
            "limit": limit,
        },
        "refusals": refusal_rows,
        "refusal_count": len(refusal_rows),
        "vendor_access": vendor_rows,
        "vendor_access_count": len(vendor_rows),
    }


@router.get("/ai-programs")
def ai_program_inventory(
    user: CurrentUser = Depends(current_user),
    since: Optional[datetime] = Query(None, description="Filter to reports signed at or after this ISO datetime"),
    until: Optional[datetime] = Query(None, description="Filter to reports signed at or before this ISO datetime"),
):
    """F16 — AI Program Inventory. Aggregates every distinct AI program
    (name + version) that has produced a signed §13663 official report
    in this tenant, with usage counts and a sample report id per program.
    Powers the SB-524 annual attestation."""
    qs = Report.objects(tenant_id=user.tenant_id,
                        status__in=[ReportStatus.SIGNED.value, ReportStatus.EXPORTED.value])
    if since:
        qs = qs.filter(signed_at__gte=since)
    if until:
        qs = qs.filter(signed_at__lte=until)

    by_program: dict[tuple[str, str], dict] = {}
    for r in qs:
        for p in (r.ai_programs_used or []):
            key = (p.name or "", p.version or "")
            entry = by_program.setdefault(key, {
                "name": p.name, "version": p.version, "provider": p.provider,
                "report_count": 0,
                "first_used": None, "last_used": None,
                "sample_report_id": None, "sample_report_title": None,
            })
            entry["report_count"] += 1
            if r.signed_at:
                if entry["first_used"] is None or r.signed_at < entry["first_used"]:
                    entry["first_used"] = r.signed_at
                if entry["last_used"] is None or r.signed_at > entry["last_used"]:
                    entry["last_used"] = r.signed_at
            if entry["sample_report_id"] is None:
                entry["sample_report_id"] = str(r.id)
                entry["sample_report_title"] = r.title

    programs = sorted(
        by_program.values(),
        key=lambda e: (-e["report_count"], e.get("name") or ""),
    )
    for e in programs:
        e["first_used"] = e["first_used"].isoformat() if e["first_used"] else None
        e["last_used"] = e["last_used"].isoformat() if e["last_used"] else None

    return {
        "programs": programs,
        "filter": {
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
        },
        "total_signed_reports_in_window": qs.count(),
        "distinct_program_count": len(programs),
    }


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
