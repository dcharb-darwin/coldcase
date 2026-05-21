"""Hypothesis — a detective's working theory about a case.

The detective brain-dumps freely (typed text, voice memo in browser, or
uploaded audio file). The brain-dump becomes a `BrainDump` artifact that
preserves the raw input + transcript + AI extraction lineage. AI proposes
candidate `Hypothesis` records; the detective approves which to formally
investigate. Approved hypotheses live alongside the case until the
detective marks them confirmed, disproved, or superseded.

Retention follows the case's retention policy — these are part of the
official record, like edits to reports. Audio is not auto-purged after
transcription.

Why a new artifact instead of a Note? Hypotheses are claims with status,
supporting evidence, contradicting evidence. Notes are scratch. The two
have different lifecycle semantics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from mongoengine import (
    Document as MEDocument,
    StringField, DateTimeField, ReferenceField, EmbeddedDocumentField,
    EmbeddedDocument, IntField, ListField,
)

from models.case import Case


class BrainDumpSource(str, Enum):
    TYPED = "typed"           # detective typed into the textarea
    AUDIO_RECORDED = "audio_recorded"  # captured in-portal via MediaRecorder
    AUDIO_UPLOADED = "audio_uploaded"  # drag-dropped file (.m4a / .mp3 / .wav)


class BrainDump(MEDocument):
    """The raw input that feeds the AI hypothesis extractor.

    Persisted so the lineage is intact: detective brain-dump (audio or
    typed) → transcript → AI-proposed hypotheses → detective-approved
    investigations. PRA / discovery responses can trace any approved
    hypothesis back to the original brain-dump that surfaced it.
    """

    meta = {
        "collection": "brain_dumps",
        "indexes": [
            ("tenant_id", "case", "-created_at"),
        ],
    }

    tenant_id = StringField(required=True)
    case = ReferenceField(Case, required=True)

    source = StringField(
        required=True, default=BrainDumpSource.TYPED.value,
        choices=[s.value for s in BrainDumpSource],
    )
    # Raw audio: external artifact_store reference (URI returned by the
    # storage provider). Empty for `TYPED` brain-dumps.
    audio_artifact_uri = StringField(default="")
    audio_filename = StringField(default="")
    audio_mime_type = StringField(default="")
    audio_duration_seconds = StringField(default="")  # stored as str — provider may not always return

    # Transcript — editable by the detective before extraction. For audio
    # brain-dumps this is the transcription provider's output (Whisper /
    # local model / etc.) which the detective may correct (proper nouns,
    # badge numbers, dates).
    transcript = StringField(default="")
    transcript_model = StringField(default="")  # provider name + version

    created_by = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "case_id": str(self.case.id) if self.case else None,
            "source": self.source,
            "audio_artifact_uri": self.audio_artifact_uri,
            "audio_filename": self.audio_filename,
            "audio_mime_type": self.audio_mime_type,
            "audio_duration_seconds": self.audio_duration_seconds,
            "transcript": self.transcript,
            "transcript_model": self.transcript_model,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class HypothesisStatus(str, Enum):
    INVESTIGATING = "investigating"   # detective accepted; actively working on it
    CONFIRMED = "confirmed"           # evidence supports it
    DISPROVED = "disproved"           # evidence rules it out
    SUPERSEDED = "superseded"         # replaced by a different hypothesis


class HypothesisOrigin(str, Enum):
    """Who/what surfaced this hypothesis. Multi-agent provenance so the
    detective sees at a glance whose framing they're looking at, and the
    city attorney can answer "which AI agent produced this artifact"
    during PRA / discovery review."""
    HUMAN_TYPED = "human_typed"              # detective typed it into the editor
    AI_FROM_BRAINDUMP = "ai_from_braindump"  # generator agent, from a brain dump
    AI_DE_NOVO = "ai_de_novo"                # de-novo generator, case docs only
    AI_ALTERNATIVE = "ai_alternative"        # red-team agent proposed as alternative


class HypothesisFindingKind(str, Enum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    GAP = "gap"


class HypothesisFinding(EmbeddedDocument):
    """A piece of evidence the AI cross-check produced. The detective
    accepts findings individually — same pattern as tag/person suggesters."""
    kind = StringField(required=True, choices=[k.value for k in HypothesisFindingKind])
    excerpt = StringField(default="")
    rationale = StringField(default="")
    source_doc_id = StringField(default="")
    source_doc_filename = StringField(default="")
    accepted_by = StringField(default="")
    accepted_at = DateTimeField()
    suggested_by_model = StringField(default="")

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "excerpt": self.excerpt,
            "rationale": self.rationale,
            "source_doc_id": self.source_doc_id,
            "source_doc_filename": self.source_doc_filename,
            "accepted_by": self.accepted_by,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "suggested_by_model": self.suggested_by_model,
        }


class Hypothesis(MEDocument):
    """A working theory the detective has chosen to formally investigate."""

    meta = {
        "collection": "hypotheses",
        "indexes": [
            ("tenant_id", "case", "-updated_at"),
            ("tenant_id", "case", "status"),
        ],
    }

    tenant_id = StringField(required=True)
    case = ReferenceField(Case, required=True)

    title = StringField(required=True, max_length=300)
    body = StringField(default="")          # detective-editable markdown
    rationale = StringField(default="")     # AI's rationale when it was proposed

    status = StringField(
        required=True, default=HypothesisStatus.INVESTIGATING.value,
        choices=[s.value for s in HypothesisStatus],
    )
    origin = StringField(
        required=True, default=HypothesisOrigin.HUMAN_TYPED.value,
        choices=[o.value for o in HypothesisOrigin],
    )
    # When origin=AI_ALTERNATIVE, the red-team run that surfaced this
    # hypothesis was challenging this parent. Lineage is preserved so the
    # detective can navigate parent ↔ children, and so PRA / discovery
    # review can trace the alternative back to its progenitor.
    parent_hypothesis_id = StringField(default="")
    # Closed-vocab bias flags surfaced by red-team passes against this
    # hypothesis. Accrues across runs; once flagged a bias stays flagged
    # (no dismissal mechanism — bias flags belong in the record).
    bias_flags = ListField(StringField(), default=list)
    # Logical gaps the red-team identified — things the hypothesis assumes
    # but does not establish. Free-text strings since the gaps are
    # case-specific by nature; not a closed vocab.
    logical_gaps = ListField(StringField(), default=list)
    # How many times red_team has been run against this hypothesis. Shown
    # on the card so detective knows whether it's been stress-tested.
    red_team_count = IntField(default=0)

    # If this hypothesis originated from a BrainDump (vs hand-typed),
    # keep the lineage. Optional.
    brain_dump = ReferenceField(BrainDump, required=False)

    # AI provenance — the model that proposed this hypothesis. Manual
    # hypotheses leave these empty.
    proposed_by_model = StringField(default="")
    proposed_at = DateTimeField()
    accepted_by = StringField(default="")
    accepted_at = DateTimeField()

    # Findings accumulated over the life of the hypothesis. Each
    # /check call appends more; the detective accepts the ones that
    # matter so unaccepted ones can be filtered out later.
    findings = ListField(EmbeddedDocumentField(HypothesisFinding), default=list)

    created_by = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_by = StringField(default="")
    updated_at = DateTimeField(default=datetime.utcnow)
    status_changed_at = DateTimeField()

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "case_id": str(self.case.id) if self.case else None,
            "title": self.title,
            "body": self.body,
            "rationale": self.rationale,
            "status": self.status,
            "origin": self.origin,
            "parent_hypothesis_id": self.parent_hypothesis_id or "",
            "bias_flags": list(self.bias_flags or []),
            "logical_gaps": list(self.logical_gaps or []),
            "red_team_count": int(self.red_team_count or 0),
            "brain_dump_id": str(self.brain_dump.id) if self.brain_dump else None,
            "proposed_by_model": self.proposed_by_model,
            "proposed_at": self.proposed_at.isoformat() if self.proposed_at else None,
            "accepted_by": self.accepted_by,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "findings": [f.to_dict() for f in (self.findings or [])],
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status_changed_at": self.status_changed_at.isoformat() if self.status_changed_at else None,
        }
