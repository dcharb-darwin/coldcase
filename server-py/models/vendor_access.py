"""VendorAccessRequest — F10.

Every time Darwin operations staff need to access agency data under one
of the §13663(d)(iii) carve-out purposes, they open a request here. An
agency admin approves or denies. Each actual data pull during the
validity window calls `record-access`, which fails 403 if status ≠
approved or `expires_at < now`.

This is the software enforcement of business rule #23.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from mongoengine import (
    Document as MEDocument, StringField, DateTimeField, ListField,
    DictField, IntField,
)


class VendorAccessPurpose(str, Enum):
    TROUBLESHOOTING = "troubleshooting"
    BIAS_MITIGATION = "bias_mitigation"
    ACCURACY_IMPROVEMENT = "accuracy_improvement"
    SYSTEM_REFINEMENT = "system_refinement"


class VendorAccessStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    REVOKED = "revoked"


class VendorAccessRequest(MEDocument):
    meta = {
        "collection": "vendor_access_requests",
        "indexes": [
            ("tenant_id", "-requested_at"),
            "status",
            ("tenant_id", "status"),
            "requesting_operator_id",
            "expires_at",
        ],
    }

    tenant_id = StringField(required=True)  # the agency whose data is in scope
    requesting_operator_id = StringField(required=True)  # the Darwin engineer
    requesting_operator_display = StringField(default="")

    purpose = StringField(required=True, choices=[p.value for p in VendorAccessPurpose])
    reason_detail = StringField(required=True)  # free text

    scope_kind = StringField(required=True, choices=["tenant_wide", "case_ids", "report_ids"])
    scope_case_ids = ListField(StringField(), default=list)
    scope_report_ids = ListField(StringField(), default=list)

    requested_at = DateTimeField(default=datetime.utcnow)
    expires_at = DateTimeField(required=True)

    status = StringField(
        required=True, default=VendorAccessStatus.PENDING.value,
        choices=[s.value for s in VendorAccessStatus],
    )
    approved_by = StringField(default="")
    approved_at = DateTimeField()
    denied_by = StringField(default="")
    denied_at = DateTimeField()
    denial_reason = StringField(default="")
    revoked_by = StringField(default="")
    revoked_at = DateTimeField()

    # Append-only usage log: each time the approved operator pings
    # /record-access, a {timestamp, note} entry is appended.
    accessed_at = ListField(DictField(), default=list)
    use_count = IntField(default=0)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "tenant_id": self.tenant_id,
            "requesting_operator_id": self.requesting_operator_id,
            "requesting_operator_display": self.requesting_operator_display,
            "purpose": self.purpose,
            "reason_detail": self.reason_detail,
            "scope_kind": self.scope_kind,
            "scope_case_ids": list(self.scope_case_ids or []),
            "scope_report_ids": list(self.scope_report_ids or []),
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "denied_by": self.denied_by,
            "denied_at": self.denied_at.isoformat() if self.denied_at else None,
            "denial_reason": self.denial_reason,
            "revoked_by": self.revoked_by,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "accessed_at": list(self.accessed_at or []),
            "use_count": self.use_count,
        }


def expires_default(hours: int = 24) -> datetime:
    return datetime.utcnow() + timedelta(hours=hours)
