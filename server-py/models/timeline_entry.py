"""TimelineEntry — case-scoped dated event the detective curates.

Distinct from `AuditEvent` (which is the immutable system-side audit log
of every state change). A `TimelineEntry` is the detective's own
chronology of the case: "1945-08-15 12:00 Letha leaves to borrow rice",
"1945-08-15 17:00 Nolan returns home, finds Letha missing", etc.

Phase B: manual entry. Phase C: LLM-extracted candidates that the
detective accepts/rejects. The accepted shape is identical — the
provenance lives in `source` ("manual" vs "ai_suggested").
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, ReferenceField,
)

from models.case import Case


class TimelineEntrySource(str, Enum):
    MANUAL = "manual"
    AI_SUGGESTED = "ai_suggested"


class TimelineEntry(MEDocument):
    meta = {
        "collection": "timeline_entries",
        "indexes": [
            ("tenant_id", "case", "occurred_at"),
            "-created_at",
        ],
    }

    tenant_id = StringField(required=True)
    case = ReferenceField(Case, required=True)

    # When the underlying event happened. Stored as a free-form string so
    # uncertain dates ("circa 1945-08-15", "summer 1945") survive — the
    # LLM and the detective both routinely produce these.
    occurred_at = StringField(required=True)
    # One-line event label. The narrative goes in `notes`.
    label = StringField(required=True)
    notes = StringField(default="")
    # The doc that backs this event — optional, but lets the citation
    # chip pattern wire through to the source line in the future.
    source_document_id = StringField(default="")

    source = StringField(
        required=True, default=TimelineEntrySource.MANUAL.value,
        choices=[s.value for s in TimelineEntrySource],
    )
    # Free-text rationale, populated when source == ai_suggested.
    rationale = StringField(default="")

    created_by = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "case_id": str(self.case.id) if self.case else None,
            "occurred_at": self.occurred_at,
            "label": self.label,
            "notes": self.notes,
            "source_document_id": self.source_document_id,
            "source": self.source,
            "rationale": self.rationale,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
