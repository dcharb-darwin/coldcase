"""Report — the §13663 'official report'.

Created from a chosen assistant Message ("first AI draft"). The officer may
edit the final text freely before signing, but the linked first-draft Message
is locked and immutable. Once signed (`status=signed`), the Report itself
is immutable.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, ListField, IntField,
    ReferenceField, DictField, BooleanField, EmbeddedDocument, EmbeddedDocumentField,
)

from models.case import Case
from models.conversation import Conversation
from models.message import Message


class ReportStatus(str, Enum):
    DRAFT = "draft"
    SIGNED = "signed"
    EXPORTED = "exported"
    SUPERSEDED = "superseded"  # if a revision is signed later, the prior is marked superseded but never deleted


class AIProgram(EmbeddedDocument):
    """Identification of an AI program used to generate any portion of a report.
    Penal Code §13663(a)(1) requires this on the report itself."""
    name = StringField(required=True)       # e.g. "GCC Copilot"
    version = StringField(default="")        # e.g. "gpt-4o-2024-08-06" or vendor build id
    provider = StringField(default="")       # e.g. "Microsoft 365 Copilot (GCC)"


class ReportRevision(EmbeddedDocument):
    """Append-only revision snapshot. Created on every PATCH and on initial
    promote. The first revision (`seq=0`) is the verbatim AI first draft."""
    seq = IntField(required=True)
    text = StringField(required=True)
    editor_id = StringField(required=True)
    editor_display = StringField(default="")
    timestamp = DateTimeField(required=True)
    content_sha256 = StringField(required=True)
    byte_count = IntField(default=0)
    note = StringField(default="")  # optional human note, e.g. "promoted from AI" / "officer edit"


class OfficerSignature(EmbeddedDocument):
    """§13663(a)(2). The officer attests they reviewed contents and that the
    facts contained in the report are true and correct."""
    user_id = StringField(required=True)
    display_name = StringField(default="")
    badge_number = StringField(default="")
    signed_at = DateTimeField(required=True)
    ip_address = StringField(default="")
    content_sha256 = StringField(required=True)  # hash of final_text at sign time
    attestation_text = StringField(
        default=(
            "I have reviewed the contents of this report and certify under "
            "penalty of perjury that the facts contained herein are true and correct."
        )
    )


class Report(MEDocument):
    meta = {
        "collection": "reports",
        "indexes": [
            "case",
            ("first_ai_draft_message_id",),
            "status",
            "-signed_at",
        ],
    }

    tenant_id = StringField(required=True)
    case = ReferenceField(Case, required=True)
    conversation = ReferenceField(Conversation, required=True)

    title = StringField(required=True)
    final_text = StringField(required=True)        # what the officer is signing
    first_ai_draft_message_id = StringField(required=True)  # the §13663(b) "first draft"
    first_ai_draft_text_snapshot = StringField(required=True)  # frozen copy of the message content at promote-time

    # §13663(a)(1) — at least one entry is required at sign-time.
    ai_programs_used = ListField(EmbeddedDocumentField(AIProgram), default=list)

    # §13663(a)(1) — exact statutory disclosure. Hardcoded; included verbatim on every page of the export.
    statutory_disclosure = StringField(
        default="This report was written either fully or in part using artificial intelligence.",
    )

    status = StringField(
        required=True, default=ReportStatus.DRAFT.value,
        choices=[s.value for s in ReportStatus],
    )

    signature = EmbeddedDocumentField(OfficerSignature)

    # Append-only edit history. seq=0 is the verbatim AI first draft.
    revisions = ListField(EmbeddedDocumentField(ReportRevision), default=list)

    # Export
    exported_artifact_uri = StringField(default="")
    export_target = StringField(default="")  # "evidence.com" | "file" | …
    exported_at = DateTimeField()

    # Lineage
    supersedes_report_id = StringField()  # if this is a revision of an earlier signed report

    created_by = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    signed_at = DateTimeField()

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "case_id": str(self.case.id) if self.case else None,
            "conversation_id": str(self.conversation.id) if self.conversation else None,
            "title": self.title,
            "final_text": self.final_text,
            "first_ai_draft_message_id": self.first_ai_draft_message_id,
            "first_ai_draft_text_snapshot": self.first_ai_draft_text_snapshot,
            "ai_programs_used": [
                {"name": p.name, "version": p.version, "provider": p.provider}
                for p in (self.ai_programs_used or [])
            ],
            "statutory_disclosure": self.statutory_disclosure,
            "status": self.status,
            "signature": (
                {
                    "user_id": self.signature.user_id,
                    "display_name": self.signature.display_name,
                    "badge_number": self.signature.badge_number,
                    "signed_at": self.signature.signed_at.isoformat() if self.signature.signed_at else None,
                    "content_sha256": self.signature.content_sha256,
                    "attestation_text": self.signature.attestation_text,
                }
                if self.signature else None
            ),
            "revisions": [
                {
                    "seq": r.seq,
                    "text": r.text,
                    "editor_id": r.editor_id,
                    "editor_display": r.editor_display,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    "content_sha256": r.content_sha256,
                    "byte_count": r.byte_count,
                    "note": r.note,
                    "is_signed_revision": (
                        bool(self.signature)
                        and self.signature.content_sha256 == r.content_sha256
                    ),
                }
                for r in (self.revisions or [])
            ],
            "exported_artifact_uri": self.exported_artifact_uri,
            "export_target": self.export_target,
            "exported_at": self.exported_at.isoformat() if self.exported_at else None,
            "supersedes_report_id": self.supersedes_report_id,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
        }
