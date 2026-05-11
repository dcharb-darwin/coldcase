"""Case — investigative case folder."""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, ListField, BooleanField,
)


class CaseStatus(str, Enum):
    OPEN = "open"
    ACTIVE = "active"
    CLOSED = "closed"
    REOPENED = "reopened"


class CaseClassification(str, Enum):
    HOMICIDE = "homicide"
    ROBBERY = "robbery"
    ASSAULT = "assault"
    BURGLARY = "burglary"
    SEXUAL_ASSAULT = "sexual_assault"
    MISSING_PERSON = "missing_person"
    OTHER = "other"


class RetentionPolicy(str, Enum):
    """Per Penal Code §13663(b), first AI draft retention follows the report.
    `MATCH_OFFICIAL_REPORT` is the safe default; longer floors are agency choice."""
    MATCH_OFFICIAL_REPORT = "match_official_report"
    SEVEN_YEARS = "7y"
    INDEFINITE = "indefinite"


class Case(MEDocument):
    meta = {
        "collection": "cases",
        "indexes": [
            {"fields": ["tenant_id", "case_number"], "unique": True},
            "status",
            "classification",
            ("tenant_id", "-created_at"),
        ],
    }

    tenant_id = StringField(required=True)
    app_id = StringField(required=True, default="coldcase")

    case_number = StringField(required=True)
    title = StringField(required=True)
    classification = StringField(
        required=True, default=CaseClassification.OTHER.value,
        choices=[c.value for c in CaseClassification],
    )
    status = StringField(
        required=True, default=CaseStatus.OPEN.value,
        choices=[s.value for s in CaseStatus],
    )
    retention_policy = StringField(
        required=True, default=RetentionPolicy.MATCH_OFFICIAL_REPORT.value,
        choices=[r.value for r in RetentionPolicy],
    )
    # Detective assigned + co-investigators
    primary_investigator_id = StringField(required=True)
    co_investigator_ids = ListField(StringField(), default=list)

    description = StringField(default="")

    created_by = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    closed_at = DateTimeField()
    closed_by = StringField()
    last_activity_at = DateTimeField(default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "case_number": self.case_number,
            "title": self.title,
            "classification": self.classification,
            "status": self.status,
            "retention_policy": self.retention_policy,
            "primary_investigator_id": self.primary_investigator_id,
            "co_investigator_ids": list(self.co_investigator_ids or []),
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None,
        }
