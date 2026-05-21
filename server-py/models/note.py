"""Note — detective freeform scratch, scoped to case/document/report.

Distinct from `Tag` (closed agency vocabulary, legally durable, filterable)
and `TimelineEntry` (dated case event). A Note is a one-off thought:
"check whether the gun came back from CBI lab", "ask DA about §187 vs §190",
"interview Jane on Monday". Plain markdown body, last-edited timestamp.

Per docs/design/workflow-and-ux.md §11 decision #2 — the closed-vocab
tag set is for things the city attorney will filter on years later; this
is for the detective's working memory in the moment.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, ReferenceField,
)

from models.case import Case


class NoteSubjectKind(str, Enum):
    CASE = "case"
    DOCUMENT = "document"
    REPORT = "report"


class Note(MEDocument):
    meta = {
        "collection": "notes",
        "indexes": [
            ("tenant_id", "case", "-updated_at"),
            ("tenant_id", "subject_kind", "subject_id", "-updated_at"),
        ],
    }

    tenant_id = StringField(required=True)
    # Every note belongs to a case (the searchable rollup unit) — even
    # doc-scoped and report-scoped notes are case-rooted.
    case = ReferenceField(Case, required=True)

    subject_kind = StringField(
        required=True, default=NoteSubjectKind.CASE.value,
        choices=[k.value for k in NoteSubjectKind],
    )
    subject_id = StringField(required=True)

    # Threaded replies. A reply note carries the parent's id; top-level
    # notes have parent_note_id="". Replies inherit the parent's
    # subject_kind + subject_id (validated server-side) so a thread is
    # always rooted in one subject (no cross-subject threads).
    parent_note_id = StringField(default="")

    body = StringField(required=True)

    created_by = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_by = StringField(default="")
    updated_at = DateTimeField(default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "case_id": str(self.case.id) if self.case else None,
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "parent_note_id": self.parent_note_id or "",
            "body": self.body,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
