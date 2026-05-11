"""Conversation — chat session against a case."""

from __future__ import annotations
from datetime import datetime

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, ReferenceField,
)

from models.case import Case


class Conversation(MEDocument):
    meta = {
        "collection": "conversations",
        "indexes": [
            "case",
            ("tenant_id", "-started_at"),
            "user_id",
        ],
    }

    tenant_id = StringField(required=True)
    case = ReferenceField(Case, required=True)
    user_id = StringField(required=True)
    title = StringField(default="")
    started_at = DateTimeField(default=datetime.utcnow)
    last_message_at = DateTimeField(default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "case_id": str(self.case.id) if self.case else None,
            "user_id": self.user_id,
            "title": self.title,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
        }
