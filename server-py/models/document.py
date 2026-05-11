"""Document — pointer to a file in agency storage. Cold Case never holds the binary."""

from __future__ import annotations
from datetime import datetime

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, IntField, ReferenceField,
)

from models.case import Case


class Document(MEDocument):
    meta = {
        "collection": "documents",
        "indexes": [
            "case",
            ("tenant_id", "sha256"),
            "-uploaded_at",
        ],
    }

    tenant_id = StringField(required=True)
    case = ReferenceField(Case, required=True)

    # Pointer-only; binary lives in agency Azure / S3.
    storage_uri = StringField(required=True)
    sha256 = StringField(required=True)
    original_filename = StringField(required=True)
    mime_type = StringField(default="application/pdf")
    page_count = IntField(default=0)
    size_bytes = IntField(default=0)

    uploaded_by = StringField(required=True)
    uploaded_at = DateTimeField(default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "case_id": str(self.case.id) if self.case else None,
            "storage_uri": self.storage_uri,
            "sha256": self.sha256,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "page_count": self.page_count,
            "size_bytes": self.size_bytes,
            "uploaded_by": self.uploaded_by,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }
