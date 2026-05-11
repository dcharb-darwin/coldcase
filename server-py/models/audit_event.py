"""AuditEvent — append-only audit log.

Distinct from `services/audit.py` (admin-pattern audit). This is the *domain*
audit log §13663(c) is concerned with. Every state change worth defending in
court should land here.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, DictField,
)


class AuditEventType(str, Enum):
    CASE_CREATED = "case.created"
    CASE_UPDATED = "case.updated"
    CASE_CLOSED = "case.closed"
    CASE_REOPENED = "case.reopened"
    DOCUMENT_REGISTERED = "document.registered"
    MEDIA_REGISTERED = "media.registered"
    CONVERSATION_STARTED = "conversation.started"
    MESSAGE_USER = "message.user"
    MESSAGE_ASSISTANT = "message.assistant"
    REPORT_DRAFTED = "report.drafted"
    REPORT_EDITED = "report.edited"
    REPORT_SIGNED = "report.signed"
    REPORT_EXPORTED = "report.exported"
    APPROVAL_GIVEN = "approval.given"
    RETENTION_CHANGED = "retention.changed"
    CASE_DISCOVERY_EXPORTED = "case.discovery_exported"
    VENDOR_ACCESS_REQUESTED = "vendor.access.requested"
    VENDOR_ACCESS_APPROVED = "vendor.access.approved"
    VENDOR_ACCESS_DENIED = "vendor.access.denied"
    VENDOR_ACCESS_REVOKED = "vendor.access.revoked"
    VENDOR_ACCESS_USED = "vendor.access.used"
    VENDOR_ACCESS_SCOPE_VIOLATION = "vendor.access.scope_violation"
    PURGE_BLOCKED = "purge.blocked"             # §13663(b) refused a purge
    FIRST_DRAFT_MUTATION_BLOCKED = "first_draft.mutation_blocked"


class AuditEvent(MEDocument):
    meta = {
        "collection": "audit_events",
        "indexes": [
            ("tenant_id", "-timestamp"),
            ("case_id", "-timestamp"),
            ("user_id", "-timestamp"),
            ("event_type", "-timestamp"),
            ("report_id", "-timestamp"),
        ],
    }

    tenant_id = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    event_type = StringField(required=True, choices=[e.value for e in AuditEventType])

    user_id = StringField(required=True)
    user_display = StringField(default="")
    ip_address = StringField(default="")

    case_id = StringField()
    conversation_id = StringField()
    message_id = StringField()
    report_id = StringField()
    document_id = StringField()
    media_id = StringField()

    summary = StringField(default="")
    detail = DictField(default=dict)  # event-specific payload (old/new values, reason, etc.)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type,
            "user_id": self.user_id,
            "user_display": self.user_display,
            "ip_address": self.ip_address,
            "case_id": self.case_id,
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "report_id": self.report_id,
            "document_id": self.document_id,
            "media_id": self.media_id,
            "summary": self.summary,
            "detail": dict(self.detail or {}),
        }
