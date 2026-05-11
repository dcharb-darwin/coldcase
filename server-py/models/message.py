"""Message — single user prompt or assistant response in a Conversation.

Once persisted, a Message is immutable. The first assistant Message that gets
promoted to a Report is flagged `is_first_ai_draft=True` and additionally
locked from any deletion path (Penal Code §13663(b)).
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, IntField, ListField,
    BooleanField, ReferenceField, DictField,
)

from models.conversation import Conversation


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(MEDocument):
    meta = {
        "collection": "messages",
        "indexes": [
            ("conversation", "timestamp"),
            "parent_message_id",
            "is_first_ai_draft",
            "user_id",
        ],
        # MongoEngine doesn't enforce immutability — see services/messages.py
        # for the persistence helper that enforces append-only.
    }

    tenant_id = StringField(required=True)
    conversation = ReferenceField(Conversation, required=True)

    role = StringField(required=True, choices=[r.value for r in MessageRole])
    content = StringField(required=True)
    parent_message_id = StringField()  # ObjectId of the user message this responds to, or the prior assistant re-ask
    user_id = StringField(required=True)  # human who issued the prompt or who triggered the assistant call
    timestamp = DateTimeField(default=datetime.utcnow)

    # AI metadata — present on assistant messages
    model = StringField(default="")           # e.g. "gcc-copilot:gpt-4o-2024-08-06"
    provider = StringField(default="")         # "gcc_copilot" | "ollama" | …
    prompt_tokens = IntField(default=0)
    completion_tokens = IntField(default=0)
    in_context_document_ids = ListField(StringField(), default=list)
    in_context_media_ids = ListField(StringField(), default=list)
    extra = DictField(default=dict)            # provider-specific request id / etc.

    # §13663 lineage flags
    is_first_ai_draft = BooleanField(default=False)
    first_draft_locked_for_report_id = StringField()  # set when a Report is created from this message; immutable thereafter

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation.id) if self.conversation else None,
            "role": self.role,
            "content": self.content,
            "parent_message_id": self.parent_message_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "model": self.model,
            "provider": self.provider,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "in_context_document_ids": list(self.in_context_document_ids or []),
            "in_context_media_ids": list(self.in_context_media_ids or []),
            "is_first_ai_draft": bool(self.is_first_ai_draft),
            "first_draft_locked_for_report_id": self.first_draft_locked_for_report_id,
            "extra": dict(self.extra or {}),
        }
