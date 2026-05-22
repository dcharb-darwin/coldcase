"""PersonIdentityAssertion — officer-confirmed verdict on whether two
Person records refer to the same individual.

Overrides the heuristic plausibility scorer. When the detective marks
two persons as "same" or "different", that verdict carries 1.0
confidence through every downstream graph query — clustering, conflict
detection, neighborhood traversal.

The verdict is per ordered pair of Person ids. We normalize to a
canonical ordering (a < b lexicographically) so both directions
resolve to the same row.

Audited via PERSON_IDENTITY_ASSERTED events on the hash chain so
PRA / discovery review can trace who made which call and when.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from mongoengine import (
    Document as MEDocument,
    StringField, DateTimeField,
)


class IdentityVerdict(str, Enum):
    SAME = "same"
    DIFFERENT = "different"


class PersonIdentityAssertion(MEDocument):
    meta = {
        "collection": "person_identity_assertions",
        "indexes": [
            # One verdict per ordered pair; updates replace rather than
            # accrete.
            {
                "fields": ["tenant_id", "person_a_id", "person_b_id"],
                "unique": True,
            },
            ("tenant_id", "verdict"),
        ],
    }

    tenant_id = StringField(required=True)
    # Canonical ordering: person_a_id < person_b_id lexicographically.
    # Callers go through `normalize_pair` so the constraint can rely on it.
    person_a_id = StringField(required=True)
    person_b_id = StringField(required=True)

    verdict = StringField(
        required=True, choices=[v.value for v in IdentityVerdict],
    )
    rationale = StringField(default="")

    asserted_by = StringField(required=True)
    asserted_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "person_a_id": self.person_a_id,
            "person_b_id": self.person_b_id,
            "verdict": self.verdict,
            "rationale": self.rationale,
            "asserted_by": self.asserted_by,
            "asserted_at": self.asserted_at.isoformat() if self.asserted_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def normalize_pair(a: str, b: str) -> tuple[str, str]:
    """Return (lexicographically-smaller, larger). Match the index."""
    return (a, b) if a < b else (b, a)
