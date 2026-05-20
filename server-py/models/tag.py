"""Tag + TagAssignment — closed-vocabulary tagging across cases/docs/messages/reports.

Two kinds:
  - `system` tags: server-applied based on state (e.g. `signed-report-present`,
    `vendor-accessed`, `ocr-only`). Not user-mutable. Reserved for future
    auto-tagging — schema is here so the UI doesn't need a migration later.
  - `user` tags: agency-curated closed vocabulary (e.g. `#brady-relevant`,
    `#suspect`, `#alibi`). Admins manage the vocabulary; detectives apply.

Tags are intentionally **not** freeform. Per docs/design/workflow-and-ux.md
§11/decision 2 + §13.1, evidence.com's category model expects controlled
vocabularies; making tags ad-hoc would corrupt the future export. Freeform
detective shorthand belongs in a separate `Note` artifact (not yet built).

Assignments are stored as a separate document (not embedded) so we can query
"every case tagged #brady-relevant" without scanning every case.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, ListField,
)


class TagKind(str, Enum):
    SYSTEM = "system"
    USER = "user"


class TagSubjectKind(str, Enum):
    """What kind of artifact a TagAssignment binds to."""
    CASE = "case"
    DOCUMENT = "document"
    MESSAGE = "message"
    REPORT = "report"


# Palette names mirror Tailwind tokens so the frontend can render the tag
# in its declared color without round-tripping a hex.
TAG_COLOR_CHOICES = (
    "slate", "red", "amber", "emerald", "blue", "indigo", "purple", "pink",
)


class Tag(MEDocument):
    """The vocabulary entry. Created by an admin (closed vocabulary)."""

    meta = {
        "collection": "tags",
        "indexes": [
            {"fields": ["tenant_id", "slug"], "unique": True},
            ("tenant_id", "kind"),
        ],
    }

    tenant_id = StringField(required=True)
    # Human label shown in the UI (e.g. "Brady-relevant").
    label = StringField(required=True)
    # URL/api-safe slug, unique per tenant. Used in chip rendering + filter URLs.
    slug = StringField(required=True)
    # Optional one-line guidance shown in the tag-picker tooltip.
    description = StringField(default="")
    kind = StringField(
        required=True, default=TagKind.USER.value,
        choices=[k.value for k in TagKind],
    )
    color = StringField(
        required=True, default="slate",
        choices=list(TAG_COLOR_CHOICES),
    )
    # Which subject kinds may receive this tag. Empty = all kinds allowed.
    applicable_to = ListField(
        StringField(choices=[k.value for k in TagSubjectKind]),
        default=list,
    )
    created_by = StringField(default="seed")
    created_at = DateTimeField(default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "label": self.label,
            "slug": self.slug,
            "description": self.description,
            "kind": self.kind,
            "color": self.color,
            "applicable_to": list(self.applicable_to or []),
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TagAssignment(MEDocument):
    """A Tag applied to a specific artifact (case/doc/message/report)."""

    meta = {
        "collection": "tag_assignments",
        "indexes": [
            # Stop the same tag from being applied twice to the same subject.
            {
                "fields": ["tenant_id", "tag_id", "subject_kind", "subject_id"],
                "unique": True,
            },
            ("tenant_id", "subject_kind", "subject_id"),
            ("tenant_id", "tag_id"),
        ],
    }

    tenant_id = StringField(required=True)
    tag_id = StringField(required=True)
    subject_kind = StringField(
        required=True,
        choices=[k.value for k in TagSubjectKind],
    )
    subject_id = StringField(required=True)
    # Snapshot of the case the subject belongs to. Lets us filter "every
    # tag on every artifact in this case" with a single index.
    case_id = StringField()
    applied_by = StringField(required=True)
    applied_at = DateTimeField(default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "tag_id": self.tag_id,
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "case_id": self.case_id,
            "applied_by": self.applied_by,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
        }
