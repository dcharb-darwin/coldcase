"""Officer verdicts on whether two Person records are the same individual.

Overrides the heuristic plausibility scorer. POST to assert; GET to
list existing assertions for a pair (so UI can show "already
confirmed" instead of the assertion buttons); DELETE to revoke.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models import IdentityVerdict, Person, PersonIdentityAssertion, normalize_pair
from models.audit_event import AuditEventType
from routers._deps import CurrentUser, current_user, require_perm
from services import case_audit
from services.graph import get_graph_service
from services.vendor_scope import enforce_vendor_scope


router = APIRouter(
    prefix="/persons/identity-assertions", tags=["Person identity"],
    dependencies=[Depends(enforce_vendor_scope)],
)


class AssertBody(BaseModel):
    person_a_id: str = Field(min_length=1, max_length=64)
    person_b_id: str = Field(min_length=1, max_length=64)
    verdict: IdentityVerdict
    rationale: str = Field(default="", max_length=2000)


@router.post("", status_code=201)
@require_perm("case.edit")
def upsert_assertion(body: AssertBody, user: CurrentUser = Depends(current_user)):
    if body.person_a_id == body.person_b_id:
        raise HTTPException(422, "person_a_id and person_b_id must differ")
    # Validate both persons exist in this tenant.
    for pid in (body.person_a_id, body.person_b_id):
        if not Person.objects(id=pid, tenant_id=user.tenant_id).first():
            raise HTTPException(404, f"Person {pid!r} not found")

    a, b = normalize_pair(body.person_a_id, body.person_b_id)
    existing = PersonIdentityAssertion.objects(
        tenant_id=user.tenant_id, person_a_id=a, person_b_id=b,
    ).first()
    now = datetime.utcnow()
    is_new = existing is None
    if existing:
        existing.verdict = body.verdict.value
        existing.rationale = body.rationale.strip()
        existing.updated_at = now
        existing.save()
        assertion = existing
    else:
        assertion = PersonIdentityAssertion(
            tenant_id=user.tenant_id,
            person_a_id=a, person_b_id=b,
            verdict=body.verdict.value,
            rationale=body.rationale.strip(),
            asserted_by=user.user_id,
            asserted_at=now, updated_at=now,
        ).save()

    # Audit on the hash chain. We don't have a case_id directly — pick
    # one of the persons' cases for the event so timeline queries surface
    # it; if both persons belong to the same case it's unambiguous.
    case_id_for_audit: Optional[str] = None
    p_a = Person.objects(id=a, tenant_id=user.tenant_id).first()
    if p_a and p_a.case:
        case_id_for_audit = str(p_a.case.id)
    case_audit.log_user_event(
        user,
        event_type=AuditEventType.PERSON_IDENTITY_ASSERTED,
        case_id=case_id_for_audit,
        summary=(
            f"Officer asserted persons are {body.verdict.value.upper()}"
            f"{' (updated)' if not is_new else ''}"
        ),
        detail={
            "assertion_id": str(assertion.id),
            "person_a_id": a,
            "person_b_id": b,
            "verdict": body.verdict.value,
            "rationale": body.rationale,
            "was_update": not is_new,
        },
    )

    # Drop the graph cache so the next read picks up the new edge.
    try:
        get_graph_service().invalidate(user.tenant_id)
    except Exception:  # noqa: BLE001
        pass

    return assertion.to_dict()


@router.get("")
@require_perm("case.read")
def get_assertion(
    person_a_id: str, person_b_id: str,
    user: CurrentUser = Depends(current_user),
):
    a, b = normalize_pair(person_a_id, person_b_id)
    existing = PersonIdentityAssertion.objects(
        tenant_id=user.tenant_id, person_a_id=a, person_b_id=b,
    ).first()
    return {"assertion": existing.to_dict() if existing else None}


@router.delete("", status_code=204)
@require_perm("case.edit")
def revoke_assertion(
    person_a_id: str, person_b_id: str,
    user: CurrentUser = Depends(current_user),
):
    a, b = normalize_pair(person_a_id, person_b_id)
    existing = PersonIdentityAssertion.objects(
        tenant_id=user.tenant_id, person_a_id=a, person_b_id=b,
    ).first()
    if not existing:
        raise HTTPException(404, "No assertion to revoke")
    snapshot = existing.to_dict()
    existing.delete()
    case_audit.log_user_event(
        user,
        event_type=AuditEventType.PERSON_IDENTITY_ASSERTED,
        case_id=None,
        summary="Officer revoked prior identity assertion",
        detail={"revoked": snapshot},
    )
    try:
        get_graph_service().invalidate(user.tenant_id)
    except Exception:  # noqa: BLE001
        pass
    return None
