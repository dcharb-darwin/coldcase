"""MediaInput — bodycam / audio / video used as AI input. §13663(c)(2)."""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, IntField, ReferenceField,
)

from models.case import Case


class MediaSourceType(str, Enum):
    BODYCAM = "bodycam"
    DASHCAM = "dashcam"
    INTERVIEW_AUDIO = "interview_audio"
    INTERVIEW_VIDEO = "interview_video"
    CALL_RECORDING = "call_recording"
    OTHER = "other"


class MediaInput(MEDocument):
    """Pointer to media used (or potentially used) as AI input.

    Penal Code §13663(c)(2) requires audit trail of any video/audio used to
    create a report. We capture it even when the current Copilot endpoint
    cannot ingest it directly, so the link is available when ingestion
    becomes possible.
    """

    meta = {
        "collection": "media_inputs",
        "indexes": [
            "case",
            "source_type",
            ("tenant_id", "sha256"),
        ],
    }

    tenant_id = StringField(required=True)
    case = ReferenceField(Case, required=True)

    storage_uri = StringField(required=True)
    sha256 = StringField(required=True)
    source_type = StringField(
        required=True,
        choices=[s.value for s in MediaSourceType],
    )
    duration_seconds = IntField(default=0)
    captured_at = DateTimeField()  # when the media was originally recorded
    description = StringField(default="")

    registered_by = StringField(required=True)
    registered_at = DateTimeField(default=datetime.utcnow)

    # Stable id for federated systems. Defaults to `{case.external_id}:media:{id}`.
    external_id = StringField()

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "case_id": str(self.case.id) if self.case else None,
            "external_id": self.external_id or "",
            "storage_uri": self.storage_uri,
            "sha256": self.sha256,
            "source_type": self.source_type,
            "duration_seconds": self.duration_seconds,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "description": self.description,
            "registered_by": self.registered_by,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
        }
