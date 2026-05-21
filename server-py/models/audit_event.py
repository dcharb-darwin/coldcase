"""AuditEvent — append-only audit log.

Distinct from `services/audit.py` (admin-pattern audit). This is the *domain*
audit log §13663(c) is concerned with. Every state change worth defending in
court should land here.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, DictField, IntField,
)


# Genesis-event marker. The first event in a tenant's chain has no prior
# event to hash against; use a zeroed-out 64-char string so the field is
# always present and validation stays simple.
GENESIS_PREV_HASH = "0" * 64


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
    RETENTION_SWEEP_COMPLETED = "retention.sweep_completed"
    # AI-suggestion lineage. Distinct from `case.updated` so the city
    # attorney can answer "which artifacts on this case came from AI?"
    # without parsing detail blobs.
    PERSON_ACCEPTED_FROM_AI = "person.accepted_from_ai"
    TAG_ACCEPTED_FROM_AI = "tag.accepted_from_ai"
    NEXT_STEP_ACCEPTED_FROM_AI = "next_step.accepted_from_ai"
    INFERRED_MENTION_ACCEPTED_FROM_AI = "inferred_mention.accepted_from_ai"


class AuditEvent(MEDocument):
    meta = {
        "collection": "audit_events",
        "indexes": [
            ("tenant_id", "-timestamp"),
            ("case_id", "-timestamp"),
            ("user_id", "-timestamp"),
            ("event_type", "-timestamp"),
            ("report_id", "-timestamp"),
            # Per-tenant sequence is unique and monotonic. The unique index
            # is the concurrency primitive: two racing writers will collide
            # on the same `sequence` and the loser retries against the new
            # latest event. Partial filter keeps pre-backfill rows (which
            # have no sequence) out of the unique constraint.
            {
                "fields": ["tenant_id", "sequence"],
                "unique": True,
                "partialFilterExpression": {"sequence": {"$exists": True, "$gte": 0}},
            },
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

    # ── Hash chain (§13663(c) tamper-evidence) ─────────────────────────────
    # `sequence`        — monotonic per tenant; index unique. Assigned by
    #                     services.case_audit.log on insert.
    # `prev_event_hash` — sha256 hex of the prior event's `event_hash`.
    #                     First event uses GENESIS_PREV_HASH.
    # `event_hash`      — sha256 hex of (prev_event_hash || canonical(this)).
    #                     Recomputable from the stored fields; any change to
    #                     this row is detectable by the verify endpoint.
    sequence = IntField()
    prev_event_hash = StringField(default="")
    event_hash = StringField(default="")

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
            "sequence": self.sequence,
            "prev_event_hash": self.prev_event_hash or "",
            "event_hash": self.event_hash or "",
        }
