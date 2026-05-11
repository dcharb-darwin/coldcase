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

from dataclasses import dataclass, field, asdict
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

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SweepReport:
    horizon: str
    apply: bool
    inspected: int = 0
    cases_purged: int = 0
    first_drafts_preserved: int = 0
    cases: list[CaseSweepResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "horizon": self.horizon,
            "apply": self.apply,
            "inspected": self.inspected,
            "cases_purged": self.cases_purged,
            "first_drafts_preserved": self.first_drafts_preserved,
            "cases": [c.to_dict() for c in self.cases],
        }


def _case_eligible(case: Case, now: datetime) -> tuple[bool, str]:
    if not case.closed_at:
        return False, "no closed_at"
    policy = RetentionPolicy(case.retention_policy)
    if policy is RetentionPolicy.INDEFINITE:
        return False, "retention=indefinite"
    if policy is RetentionPolicy.MATCH_OFFICIAL_REPORT:
        return False, "retention tied to report (no horizon)"
    if policy is RetentionPolicy.SEVEN_YEARS:
        age = now - case.closed_at
        if age >= SEVEN_YEARS:
            return True, ""
        return False, f"closed for {age.days}d < 7y"
    return False, f"unknown policy {policy!r}"


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

        conversations = list(Conversation.objects(case=case).only("id"))
        # One query for the case's whole message set, projected to the
        # fields we actually need.
        messages = list(Message.objects(conversation__in=conversations)
                        .only("id", "is_first_ai_draft",
                              "first_draft_locked_for_report_id"))
        protected = [m for m in messages if m.is_first_ai_draft]
        purgeable_ids = [m.id for m in messages if not m.is_first_ai_draft]
        result.first_draft_messages_preserved = len(protected)
        result.messages_purged = len(purgeable_ids)
        result.conversations_purged = len(conversations)

        doc_ids = [d.id for d in Document.objects(case=case).only("id")]
        media_ids = [m.id for m in MediaInput.objects(case=case).only("id")]
        result.documents_purged = len(doc_ids)
        result.media_purged = len(media_ids)
        result.reports_kept = Report.objects(case=case).count()

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
            out.first_drafts_preserved += len(protected)

        if apply:
            if purgeable_ids:
                Message.objects(id__in=purgeable_ids).delete()
            # Only drop a conversation if no first-draft message still
            # anchors it.
            empty_convs = [
                c.id for c in conversations
                if Message.objects(conversation=c).count() == 0
            ]
            if empty_convs:
                Conversation.objects(id__in=empty_convs).delete()
            if doc_ids:
                Document.objects(id__in=doc_ids).delete()
            if media_ids:
                MediaInput.objects(id__in=media_ids).delete()
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
            out.cases_purged += 1

        out.cases.append(result)

    return out
