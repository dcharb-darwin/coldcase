"""Person — case-scoped human entity (suspect / witness / victim / officer / …).

Phase B: manually entered by the detective. Phase C will add an AI-suggested
extraction pass with detective accept/reject. The model is intentionally
generic so the same shape works whether the entry came from a human or a
model.

PersonMention (linking a Person to specific Document / Message references)
is **not** in this model — deferred until Phase C when extraction lands and
we need source-of-truth pointers. Today a Person is a free-standing case
attachment with a `notes` field for any cited evidence.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, ReferenceField,
)

from models.case import Case


class PersonRole(str, Enum):
    SUSPECT = "suspect"
    WITNESS = "witness"
    VICTIM = "victim"
    OFFICER = "officer"
    PERSON_OF_INTEREST = "person_of_interest"
    OTHER = "other"


class Person(MEDocument):
    meta = {
        "collection": "persons",
        "indexes": [
            ("tenant_id", "case", "role"),
            "-created_at",
        ],
    }

    tenant_id = StringField(required=True)
    case = ReferenceField(Case, required=True)

    name = StringField(required=True)
    role = StringField(
        required=True, default=PersonRole.OTHER.value,
        choices=[r.value for r in PersonRole],
    )
    # One-liner identifier the detective uses (DOB, alias, badge #, etc).
    # Kept loose since the schema is detective-curated.
    descriptor = StringField(default="")
    notes = StringField(default="")

    created_by = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "case_id": str(self.case.id) if self.case else None,
            "name": self.name,
            "role": self.role,
            "descriptor": self.descriptor,
            "notes": self.notes,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
