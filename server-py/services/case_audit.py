"""Cold Case domain audit logger.

Thin wrapper around `models.AuditEvent` to keep router code clean. Separate
from `services/audit.py` (admin-pattern audit) — that one is about RBAC
changes; this one is about case data + the §13663 chain of custody.
"""

from __future__ import annotations

from typing import Any

from models.audit_event import AuditEvent, AuditEventType


def log_user_event(user, /, *, event_type: AuditEventType, **kwargs) -> AuditEvent:
    """Convenience wrapper that pulls tenant_id / user_id / user_display /
    ip_address off the resolved `CurrentUser` so callers don't restate them.
    All other `log()` kwargs (summary, detail, case_id, report_id, ...) pass through.
    """
    return log(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        user_display=user.display_name,
        ip_address=user.ip_address,
        event_type=event_type,
        **kwargs,
    )


def log(
    *,
    tenant_id: str,
    user_id: str,
    event_type: AuditEventType,
    user_display: str = "",
    ip_address: str = "",
    case_id: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    report_id: str | None = None,
    document_id: str | None = None,
    media_id: str | None = None,
    summary: str = "",
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append-only audit log write. Never raises — failures are swallowed
    with a log line so they don't break the user's action."""
    try:
        return AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            user_display=user_display,
            ip_address=ip_address,
            event_type=event_type.value if isinstance(event_type, AuditEventType) else event_type,
            case_id=case_id,
            conversation_id=conversation_id,
            message_id=message_id,
            report_id=report_id,
            document_id=document_id,
            media_id=media_id,
            summary=summary,
            detail=detail or {},
        ).save()
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("audit log write failed: %s", exc)
        return None  # type: ignore[return-value]
