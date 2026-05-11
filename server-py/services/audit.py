"""Audit recording helper — fire-and-forget.

Mongo write failures never propagate to the caller. Routers log HR-visible
state changes (intake, task status, email approval/send, calendar
scheduling) via `record(...)`.

Usage:
    from services.audit import record, AuditAction, EntityType
    record(
        actor_id=DEV_USER_ID,
        action=AuditAction.EMPLOYEE_CREATE,
        entity_type=EntityType.EMPLOYEE,
        entity_id=employee.employee_id,
        message=f"Intake: {employee.first_name} {employee.last_name}",
        employee_id=employee.employee_id,
    )
"""

from __future__ import annotations

import json
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    EMPLOYEE_CREATE = "employee_create"
    EMPLOYEE_UPDATE = "employee_update"
    TASK_STATUS_CHANGE = "task_status_change"
    EMAIL_STATUS_CHANGE = "email_status_change"
    EMAIL_BULK_APPROVE = "email_bulk_approve"
    EMAIL_BULK_SEND = "email_bulk_send"
    CALENDAR_SCHEDULE = "calendar_schedule"
    TEMPLATE_ACTIVATE = "template_activate"
    NOTIFICATION_CONFIG_UPDATE = "notification_config_update"


class EntityType(str, Enum):
    EMPLOYEE = "employee"
    ONBOARDING_TASK = "onboarding_task"
    EMAIL_LOG = "email_log"
    CALENDAR_EVENT = "calendar_event"
    CHECKLIST_TEMPLATE = "checklist_template"
    NOTIFICATION_CONFIG = "notification_config"


def record(
    *,
    actor_id: str,
    action: AuditAction | str,
    entity_type: EntityType | str,
    entity_id: str | None = None,
    message: str,
    employee_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Record an audit entry. Silently logs and returns on failure."""
    try:
        from models import AuditLog

        AuditLog(
            actor_id=actor_id,
            action=action.value if isinstance(action, Enum) else action,
            entity_type=entity_type.value if isinstance(entity_type, Enum) else entity_type,
            entity_id=str(entity_id) if entity_id is not None else "",
            employee_id=employee_id or "",
            message=message[:500],
            metadata_json=json.dumps(metadata)[:2000] if metadata else "",
        ).save()
    except Exception as exc:  # noqa: BLE001 — audit must never break the caller
        logger.warning("Audit record failed: %s", exc)
