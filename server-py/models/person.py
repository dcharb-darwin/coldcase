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
    Document as MEDocument, EmbeddedDocument, EmbeddedDocumentField,
    StringField, DateTimeField, ReferenceField,
)

from models.case import Case


class PersonRole(str, Enum):
    SUSPECT = "suspect"
    WITNESS = "witness"
    VICTIM = "victim"
    OFFICER = "officer"
    PERSON_OF_INTEREST = "person_of_interest"
    OTHER = "other"


class ProvenanceSource(str, Enum):
    """How this artifact came into existence on a case."""
    MANUAL = "manual"
    AI_SUGGESTED = "ai_suggested"


class Provenance(EmbeddedDocument):
    """Uniform AI-suggestion lineage. Embedded on artifacts that can be
    either typed in by an officer OR proposed by the AI and explicitly
    accepted. Answers "which artifacts on this case came from AI?" for
    the city attorney + supports SB-524's spirit (every AI-touched
    surface is identified and traceable).

    Reused by Person, TagAssignment, future entities.
    """
    source = StringField(
        required=True, default=ProvenanceSource.MANUAL.value,
        choices=[s.value for s in ProvenanceSource],
    )
    # Exact provider-returned model id at suggestion time (e.g. the dated
    # OpenAI id) — matches the disclosure footer pattern on signed reports.
    suggested_by_model = StringField(default="")
    # One-line LLM rationale captured at accept-time. Distinct from
    # detective-editable notes on the artifact itself.
    suggested_rationale = StringField(default="")
    # Officer + timestamp of the accept gesture. Mirrors the created_by/
    # created_at on the parent doc, but kept separate so refactors that
    # add system-side mutations don't blur the "officer accepted this" fact.
    accepted_at = DateTimeField()
    accepted_by = StringField(default="")

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "suggested_by_model": self.suggested_by_model,
            "suggested_rationale": self.suggested_rationale,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "accepted_by": self.accepted_by,
        }


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

    # AI-suggestion lineage. Manual entries have `source=manual` (default);
    # accepted suggestions populate the full block. Replaces the prior
    # convention of stuffing the rationale into `notes` — that field is
    # the officer's editable workspace, not a provenance log.
    provenance = EmbeddedDocumentField(Provenance, default=Provenance)

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
            "provenance": (self.provenance.to_dict() if self.provenance else None),
        }
