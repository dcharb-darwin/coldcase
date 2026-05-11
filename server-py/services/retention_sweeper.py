"""F22 — Retention sweeper.

Walks closed cases whose retention horizon has elapsed and purges the
case shell + conversations + non-first-draft messages + Document
pointers. The §13663(b) **first-AI-draft floor** is hard-coded: any
Message with `is_first_ai_draft=True` is never purged — its content is
preserved for the lifetime of the signed report it underwrites, and the
sweeper emits a `PURGE_BLOCKED` event for visibility.

Retention horizons by `RetentionPolicy`:
  - MATCH_OFFICIAL_REPORT  → tied to the signed report's own retention.
    Conservative default: never purge from this sweeper. Agencies that
    want enforcement should configure SEVEN_YEARS.
  - SEVEN_YEARS            → eligible 7 years past `closed_at`.
  - INDEFINITE             → never eligible.

The sweeper is dry-run by default. Pass `apply=True` to actually delete.
Returns a structured report the caller can render in the admin UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from models import (
    Case, CaseStatus, Conversation, Document, MediaInput, Message, RetentionPolicy,
)
from models.audit_event import AuditEventType
from models.report import Report
from services import case_audit


SEVEN_YEARS = timedelta(days=365 * 7)


@dataclass
class CaseSweepResult:
    case_id: str
    case_number: str
    closed_at: Optional[str]
    retention_policy: str
    eligible: bool
    skipped_reason: str = ""
    first_draft_messages_preserved: int = 0
    messages_purged: int = 0
    conversations_purged: int = 0
    documents_purged: int = 0
    media_purged: int = 0
    reports_kept: int = 0  # signed reports always preserved


@dataclass
class SweepReport:
    horizon: str
    apply: bool
    inspected: int = 0
    purged: int = 0
    blocked: int = 0
    cases: list[CaseSweepResult] = field(default_factory=list)


def _case_eligible(case: Case, now: datetime) -> tuple[bool, str]:
    if case.status != CaseStatus.CLOSED.value:
        return False, "case not closed"
    if not case.closed_at:
        return False, "no closed_at"
    if case.retention_policy == RetentionPolicy.INDEFINITE.value:
        return False, "retention=indefinite"
    if case.retention_policy == RetentionPolicy.MATCH_OFFICIAL_REPORT.value:
        return False, "retention tied to report (no horizon)"
    if case.retention_policy == RetentionPolicy.SEVEN_YEARS.value:
        if now - case.closed_at >= SEVEN_YEARS:
            return True, ""
        return False, f"closed for {(now - case.closed_at).days}d < 7y"
    return False, f"unknown policy {case.retention_policy!r}"


def sweep(*, tenant_id: str, apply: bool = False,
          actor_user_id: str = "system",
          actor_display: str = "Retention Sweeper") -> SweepReport:
    """Inspect every closed case in this tenant and purge eligible
    artifacts. The first-AI-draft floor is enforced regardless of
    `apply`. Audit events are emitted on every purge or block."""
    now = datetime.utcnow()
    out = SweepReport(horizon=now.isoformat(), apply=apply)

    for case in Case.objects(tenant_id=tenant_id, status=CaseStatus.CLOSED.value):
        out.inspected += 1
        eligible, reason = _case_eligible(case, now)
        result = CaseSweepResult(
            case_id=str(case.id),
            case_number=case.case_number,
            closed_at=case.closed_at.isoformat() if case.closed_at else None,
            retention_policy=case.retention_policy,
            eligible=eligible,
            skipped_reason=reason if not eligible else "",
        )
        if not eligible:
            out.cases.append(result)
            continue

        # Walk the conversations / messages / docs.
        conversations = list(Conversation.objects(case=case))
        all_messages: list[Message] = []
        for conv in conversations:
            all_messages.extend(Message.objects(conversation=conv))

        protected = [m for m in all_messages if m.is_first_ai_draft]
        purgeable = [m for m in all_messages if not m.is_first_ai_draft]
        result.first_draft_messages_preserved = len(protected)
        result.messages_purged = len(purgeable)
        result.conversations_purged = len(conversations)

        docs = list(Document.objects(case=case))
        media = list(MediaInput.objects(case=case))
        result.documents_purged = len(docs)
        result.media_purged = len(media)

        reports = list(Report.objects(case=case))
        result.reports_kept = len(reports)

        # Visibility events
        if protected:
            case_audit.log(
                tenant_id=tenant_id, user_id=actor_user_id,
                user_display=actor_display,
                event_type=AuditEventType.PURGE_BLOCKED,
                case_id=str(case.id),
                summary=(
                    f"{len(protected)} first-AI-draft message(s) preserved "
                    "per §13663(b)"
                ),
                detail={
                    "message_ids": [str(m.id) for m in protected],
                    "report_ids": list({m.first_draft_locked_for_report_id
                                        for m in protected
                                        if m.first_draft_locked_for_report_id}),
                },
            )
            out.blocked += len(protected)

        if apply:
            # Order: messages → conversations → docs/media. Reports stay.
            for m in purgeable:
                m.delete()
            for conv in conversations:
                # Re-check: only delete the conversation if no first-draft
                # messages still reference it.
                remaining = Message.objects(conversation=conv).count()
                if remaining == 0:
                    conv.delete()
            for d in docs:
                d.delete()
            for med in media:
                med.delete()
            case_audit.log(
                tenant_id=tenant_id, user_id=actor_user_id,
                user_display=actor_display,
                event_type=AuditEventType.RETENTION_CHANGED,
                case_id=str(case.id),
                summary=(
                    f"Retention sweep purged case {case.case_number}: "
                    f"{result.messages_purged} msg, "
                    f"{result.documents_purged} doc, "
                    f"{result.media_purged} media; "
                    f"{result.first_draft_messages_preserved} first-draft preserved"
                ),
                detail={
                    "retention_policy": case.retention_policy,
                    "closed_at": case.closed_at.isoformat(),
                    "messages_purged": result.messages_purged,
                    "documents_purged": result.documents_purged,
                    "media_purged": result.media_purged,
                    "first_draft_preserved": result.first_draft_messages_preserved,
                },
            )
            out.purged += 1

        out.cases.append(result)

    return out


def to_dict(report: SweepReport) -> dict:
    return {
        "horizon": report.horizon,
        "apply": report.apply,
        "inspected": report.inspected,
        "purged": report.purged,
        "blocked_first_draft_messages": report.blocked,
        "cases": [c.__dict__ for c in report.cases],
    }
