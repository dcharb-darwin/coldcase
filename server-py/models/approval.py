"""Approval — supervisory approval of a signed Report (optional, sergeant role).

The Report's own `signature` is the §13663(a)(2) officer signature. An Approval
is an additional supervisory sign-off; it never replaces the officer's signature.
"""

from __future__ import annotations
from datetime import datetime

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, ReferenceField,
)

from models.report import Report


class Approval(MEDocument):
    meta = {
        "collection": "approvals",
        "indexes": [
            "report",
            "-approved_at",
        ],
    }

    tenant_id = StringField(required=True)
    report = ReferenceField(Report, required=True)
    approved_by = StringField(required=True)
    approved_at = DateTimeField(default=datetime.utcnow)
    notes = StringField(default="")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "report_id": str(self.report.id) if self.report else None,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "notes": self.notes,
        }
