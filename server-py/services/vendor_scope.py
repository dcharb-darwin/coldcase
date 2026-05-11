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
has `case_id`, `report_id`, or `conversation_id` in its path.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request

from models import (
    Conversation, Report, VendorAccessRequest, VendorAccessScopeKind, VendorAccessStatus,
)
from models.audit_event import AuditEventType
from routers._deps import CurrentUser, current_user
from services import case_audit


def auto_expire_if_due(req: VendorAccessRequest) -> None:
    """Flip status to EXPIRED if approved + past expiry. Idempotent.
    Shared between the vendor_access router (UI listing) and this gate
    so an expired-but-not-yet-flipped row is never silently treated as
    active or shown as APPROVED."""
    if (
        req.status == VendorAccessStatus.APPROVED.value
        and req.expires_at
        and req.expires_at < datetime.utcnow()
    ):
        req.status = VendorAccessStatus.EXPIRED.value
        req.save()


def resolve_active_scope(user: CurrentUser) -> Optional[VendorAccessRequest]:
    """Return the APPROVED + unexpired + unrevoked vendor access request
    for this operator+tenant, or None. If multiple match, the most
    recently-approved wins."""
    return (
        VendorAccessRequest.objects(
            tenant_id=user.tenant_id,
            requesting_operator_id=user.user_id,
            status=VendorAccessStatus.APPROVED.value,
            expires_at__gt=datetime.utcnow(),
        )
        .order_by("-approved_at")
        .first()
    )


def _scope_case_ids(scope: VendorAccessRequest, tenant_id: str) -> set[str]:
    """Resolve the effective set of case ids for this scope. For
    REPORT_IDS scopes we look up the cases owning each report in a
    single batch query rather than N round-trips."""
    if scope.scope_kind == VendorAccessScopeKind.CASE_IDS.value:
        return set(scope.scope_case_ids or [])
    if scope.scope_kind == VendorAccessScopeKind.REPORT_IDS.value:
        rids = list(scope.scope_report_ids or [])
        if not rids:
            return set()
        rows = Report.objects(id__in=rids, tenant_id=tenant_id).only("case")
        return {str(r.case.id) for r in rows if r.case}
    return set()


def _is_in_scope(scope: VendorAccessRequest, *, case_id: Optional[str],
                 report_id: Optional[str], tenant_id: str) -> bool:
    kind = scope.scope_kind
    if kind == VendorAccessScopeKind.TENANT_WIDE.value:
        return True
    if report_id and kind == VendorAccessScopeKind.REPORT_IDS.value:
        return report_id in set(scope.scope_report_ids or [])
    target_case = case_id
    if report_id and not target_case:
        r = Report.objects(id=report_id, tenant_id=tenant_id).only("case").first()
        target_case = str(r.case.id) if r and r.case else None
    if not target_case:
        return True  # not a case/report-scoped path
    return target_case in _scope_case_ids(scope, tenant_id)


def enforce_vendor_scope(request: Request,
                         user: CurrentUser = Depends(current_user)) -> None:
    """FastAPI dependency. No-op for users without an active vendor
    access request. For active vendors, 403s + logs if the path's
    case_id / report_id falls outside their approved scope.

    Result is cached on `request.state.vendor_scope` so applying the
    dep to nested routers / multiple endpoints within one request
    doesn't re-query Mongo."""
    # request.state has-attribute check is the cheapest first guard.
    cached = getattr(request.state, "_vendor_scope_resolved", None)
    if cached is False:
        return
    if cached is None:
        scope = resolve_active_scope(user)
        request.state._vendor_scope_resolved = scope or False
        if scope is None:
            return
    else:
        scope = cached

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
