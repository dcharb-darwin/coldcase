"""F10 — Vendor Access Portal (§13663(d) enforcement).

Lifecycle:
  POST /vendor/access-requests             (operator) → pending
  POST /vendor/access-requests/{id}/approve(admin)    → approved
  POST /vendor/access-requests/{id}/deny    (admin)    → denied
  POST /vendor/access-requests/{id}/revoke  (admin)    → revoked
  POST /vendor/access-requests/{id}/record-access (operator) → adds usage timestamp

Each transition emits a VENDOR_ACCESS_* audit event.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from models import (
    VendorAccessPurpose, VendorAccessRequest, VendorAccessStatus,
)
from models.audit_event import AuditEventType
from routers._deps import CurrentUser, current_user
from services import case_audit


router = APIRouter(prefix="/vendor/access-requests", tags=["Vendor access"])


# ── Bodies ──────────────────────────────────────────────────────────────────


class OpenRequestBody(BaseModel):
    tenant_id: Optional[str] = None  # default: requester's tenant
    purpose: VendorAccessPurpose
    reason_detail: str = Field(min_length=10, max_length=2000)
    scope_kind: str = Field(pattern="^(tenant_wide|case_ids|report_ids)$")
    scope_case_ids: list[str] = Field(default_factory=list)
    scope_report_ids: list[str] = Field(default_factory=list)
    expires_in_hours: int = Field(default=24, ge=1, le=168)  # 1h to 7d


class DenyBody(BaseModel):
    denial_reason: str = Field(min_length=3, max_length=500)


class RevokeBody(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class RecordAccessBody(BaseModel):
    note: str = Field(default="", max_length=500)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _auto_expire_if_due(req: VendorAccessRequest) -> None:
    """Flip status to EXPIRED if approved + past expiry. Idempotent."""
    if (
        req.status == VendorAccessStatus.APPROVED.value
        and req.expires_at
        and req.expires_at < datetime.utcnow()
    ):
        req.status = VendorAccessStatus.EXPIRED.value
        req.save()


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("", status_code=201)
def open_request(body: OpenRequestBody, user: CurrentUser = Depends(current_user)):
    tenant_id = body.tenant_id or user.tenant_id
    expires_at = datetime.utcnow() + timedelta(hours=body.expires_in_hours)
    req = VendorAccessRequest(
        tenant_id=tenant_id,
        requesting_operator_id=user.user_id,
        requesting_operator_display=user.display_name or user.user_id,
        purpose=body.purpose.value,
        reason_detail=body.reason_detail,
        scope_kind=body.scope_kind,
        scope_case_ids=body.scope_case_ids,
        scope_report_ids=body.scope_report_ids,
        expires_at=expires_at,
        status=VendorAccessStatus.PENDING.value,
    ).save()
    case_audit.log(
        tenant_id=tenant_id, user_id=user.user_id, user_display=user.display_name,
        ip_address=user.ip_address,
        event_type=AuditEventType.VENDOR_ACCESS_REQUESTED,
        summary=f"Vendor access requested ({body.purpose.value}, {body.scope_kind})",
        detail={
            "request_id": str(req.id),
            "purpose": body.purpose.value,
            "reason_detail": body.reason_detail[:200],
            "scope_kind": body.scope_kind,
            "scope_case_ids": body.scope_case_ids,
            "scope_report_ids": body.scope_report_ids,
            "expires_at": expires_at.isoformat(),
        },
    )
    return req.to_dict()


@router.get("")
def list_requests(
    user: CurrentUser = Depends(current_user),
    status: Optional[VendorAccessStatus] = Query(None),
    tenant_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    qs = VendorAccessRequest.objects(tenant_id=tenant_id or user.tenant_id)
    if status:
        qs = qs.filter(status=status.value)
    # Flip any past-expiry approved entries on the fly.
    rows = []
    for r in qs.order_by("-requested_at").limit(limit):
        _auto_expire_if_due(r)
        rows.append(r.to_dict())
    return {"requests": rows, "count": len(rows)}


@router.get("/{request_id}")
def get_request(request_id: str, user: CurrentUser = Depends(current_user)):
    req = VendorAccessRequest.objects(id=request_id, tenant_id=user.tenant_id).first()
    if not req:
        raise HTTPException(404, "Request not found")
    _auto_expire_if_due(req)
    return req.to_dict()


@router.post("/{request_id}/approve")
def approve_request(request_id: str, user: CurrentUser = Depends(current_user)):
    req = VendorAccessRequest.objects(id=request_id, tenant_id=user.tenant_id).first()
    if not req:
        raise HTTPException(404, "Request not found")
    if req.status != VendorAccessStatus.PENDING.value:
        raise HTTPException(409, f"Cannot approve request in status {req.status!r}")
    now = datetime.utcnow()
    req.status = VendorAccessStatus.APPROVED.value
    req.approved_by = user.user_id
    req.approved_at = now
    req.save()
    case_audit.log(
        tenant_id=req.tenant_id, user_id=user.user_id, user_display=user.display_name,
        ip_address=user.ip_address,
        event_type=AuditEventType.VENDOR_ACCESS_APPROVED,
        summary=f"Vendor access approved (req {req.id})",
        detail={"request_id": str(req.id), "purpose": req.purpose, "expires_at": req.expires_at.isoformat()},
    )
    return req.to_dict()


@router.post("/{request_id}/deny")
def deny_request(request_id: str, body: DenyBody, user: CurrentUser = Depends(current_user)):
    req = VendorAccessRequest.objects(id=request_id, tenant_id=user.tenant_id).first()
    if not req:
        raise HTTPException(404, "Request not found")
    if req.status != VendorAccessStatus.PENDING.value:
        raise HTTPException(409, f"Cannot deny request in status {req.status!r}")
    now = datetime.utcnow()
    req.status = VendorAccessStatus.DENIED.value
    req.denied_by = user.user_id
    req.denied_at = now
    req.denial_reason = body.denial_reason
    req.save()
    case_audit.log(
        tenant_id=req.tenant_id, user_id=user.user_id, user_display=user.display_name,
        ip_address=user.ip_address,
        event_type=AuditEventType.VENDOR_ACCESS_DENIED,
        summary=f"Vendor access denied (req {req.id}): {body.denial_reason[:100]}",
        detail={"request_id": str(req.id), "denial_reason": body.denial_reason},
    )
    return req.to_dict()


@router.post("/{request_id}/revoke")
def revoke_request(request_id: str, body: RevokeBody, user: CurrentUser = Depends(current_user)):
    req = VendorAccessRequest.objects(id=request_id, tenant_id=user.tenant_id).first()
    if not req:
        raise HTTPException(404, "Request not found")
    if req.status not in (VendorAccessStatus.APPROVED.value, VendorAccessStatus.PENDING.value):
        raise HTTPException(409, f"Cannot revoke request in status {req.status!r}")
    now = datetime.utcnow()
    req.status = VendorAccessStatus.REVOKED.value
    req.revoked_by = user.user_id
    req.revoked_at = now
    req.save()
    case_audit.log(
        tenant_id=req.tenant_id, user_id=user.user_id, user_display=user.display_name,
        ip_address=user.ip_address,
        event_type=AuditEventType.VENDOR_ACCESS_REVOKED,
        summary=f"Vendor access revoked (req {req.id}): {body.reason[:100]}",
        detail={"request_id": str(req.id), "reason": body.reason},
    )
    return req.to_dict()


@router.post("/{request_id}/record-access")
def record_access(request_id: str, body: RecordAccessBody, user: CurrentUser = Depends(current_user)):
    """Called by the Darwin operator each time they actually pull data
    during the approval window. Hard-fails 403 if the request isn't
    currently usable — this is the runtime gate that turns §13663(d)
    from a contract into software enforcement."""
    req = VendorAccessRequest.objects(id=request_id, tenant_id=user.tenant_id).first()
    if not req:
        raise HTTPException(404, "Request not found")
    _auto_expire_if_due(req)
    if req.status != VendorAccessStatus.APPROVED.value:
        raise HTTPException(403,
            f"Request is in status {req.status!r} — access is not permitted")
    if req.requesting_operator_id != user.user_id:
        raise HTTPException(403, "Only the requesting operator may record access")
    if req.expires_at < datetime.utcnow():
        req.status = VendorAccessStatus.EXPIRED.value
        req.save()
        raise HTTPException(403, "Access window has expired")
    req.accessed_at.append({
        "timestamp": datetime.utcnow().isoformat(),
        "note": body.note or "",
    })
    req.use_count += 1
    req.save()
    case_audit.log(
        tenant_id=req.tenant_id, user_id=user.user_id, user_display=user.display_name,
        ip_address=user.ip_address,
        event_type=AuditEventType.VENDOR_ACCESS_USED,
        summary=f"Vendor access used (req {req.id}, note: {body.note[:80]})",
        detail={
            "request_id": str(req.id),
            "use_count": req.use_count,
            "note": body.note,
        },
    )
    return {"ok": True, "use_count": req.use_count, "expires_at": req.expires_at.isoformat()}
