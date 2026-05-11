"""F20 — Vendor access scope enforcement (§13663(d) runtime gate).

When a Darwin operator has an APPROVED, unexpired, unrevoked
VendorAccessRequest, every case/report-scoped HTTP call they make must
fall inside that request's declared scope. If they reach off-scope data
we 403 the request and emit a VENDOR_ACCESS_SCOPE_VIOLATION audit event
— the software side of business rule #23.

Agency users (no active vendor access request) are unaffected. tenant_id
isolation is still enforced upstream by every router; this layer is the
narrower fence Darwin staff operate inside.

The dependency reads `request.path_params` rather than declared params
so a single `Depends(enforce_vendor_scope)` works on any handler that
has `case_id` or `report_id` in its path.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request

from models import Conversation, Report, VendorAccessRequest, VendorAccessScopeKind, VendorAccessStatus
from models.audit_event import AuditEventType
from routers._deps import CurrentUser, current_user
from services import case_audit


def resolve_active_scope(user: CurrentUser) -> Optional[VendorAccessRequest]:
    """Return the APPROVED + unexpired + unrevoked vendor access request
    for this operator+tenant, or None. If multiple match, the most
    recently-approved wins (we sort by -approved_at)."""
    now = datetime.utcnow()
    return (
        VendorAccessRequest.objects(
            tenant_id=user.tenant_id,
            requesting_operator_id=user.user_id,
            status=VendorAccessStatus.APPROVED.value,
            expires_at__gt=now,
        )
        .order_by("-approved_at")
        .first()
    )


def _case_id_for_report(report_id: str, tenant_id: str) -> Optional[str]:
    r = Report.objects(id=report_id, tenant_id=tenant_id).only("case").first()
    if not r or not r.case:
        return None
    return str(r.case.id)


def _is_in_scope(scope: VendorAccessRequest, *, case_id: Optional[str],
                 report_id: Optional[str], tenant_id: str) -> bool:
    if scope.scope_kind == VendorAccessScopeKind.TENANT_WIDE.value:
        return True
    allowed_cases = set(scope.scope_case_ids or [])
    allowed_reports = set(scope.scope_report_ids or [])
    if report_id:
        if scope.scope_kind == VendorAccessScopeKind.REPORT_IDS.value:
            return report_id in allowed_reports
        if scope.scope_kind == VendorAccessScopeKind.CASE_IDS.value:
            rc = _case_id_for_report(report_id, tenant_id)
            return rc is not None and rc in allowed_cases
    if case_id:
        if scope.scope_kind == VendorAccessScopeKind.CASE_IDS.value:
            return case_id in allowed_cases
        # report-scoped operator hitting a case route → only allowed if
        # the path's case owns one of the in-scope reports.
        if scope.scope_kind == VendorAccessScopeKind.REPORT_IDS.value:
            for rid in allowed_reports:
                if _case_id_for_report(rid, tenant_id) == case_id:
                    return True
            return False
    # No case_id and no report_id in the path → not a scoped resource.
    return True


def enforce_vendor_scope(request: Request,
                         user: CurrentUser = Depends(current_user)) -> None:
    """FastAPI dependency. No-op for users without an active vendor
    access request. For active vendors, 403s + logs if the path's
    case_id / report_id falls outside their approved scope."""
    scope = resolve_active_scope(user)
    if scope is None:
        return
    case_id = request.path_params.get("case_id")
    report_id = request.path_params.get("report_id")
    conv_id = request.path_params.get("conversation_id")
    if conv_id and not case_id:
        conv = (
            Conversation.objects(id=conv_id, tenant_id=user.tenant_id)
            .only("case").first()
        )
        if conv and conv.case:
            case_id = str(conv.case.id)
    if not case_id and not report_id:
        return
    if _is_in_scope(scope, case_id=case_id, report_id=report_id,
                    tenant_id=user.tenant_id):
        return

    case_audit.log_user_event(
        user,
        event_type=AuditEventType.VENDOR_ACCESS_SCOPE_VIOLATION,
        case_id=case_id,
        report_id=report_id,
        summary=(
            f"Off-scope access blocked: "
            f"{request.method} {request.url.path} "
            f"(scope={scope.scope_kind})"
        ),
        detail={
            "request_id": str(scope.id),
            "scope_kind": scope.scope_kind,
            "scope_case_ids": list(scope.scope_case_ids or []),
            "scope_report_ids": list(scope.scope_report_ids or []),
            "attempted_case_id": case_id,
            "attempted_report_id": report_id,
            "method": request.method,
            "path": request.url.path,
        },
    )
    raise HTTPException(
        status_code=403,
        detail="Off-scope access blocked by vendor access policy (§13663(d))",
    )
