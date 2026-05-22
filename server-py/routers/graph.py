"""Endpoints over the GraphService interface.

Thin wrappers — all logic lives in services/graph. Endpoints validate
input + render JSON. Backend swap (Mongo native, Neo4j) requires zero
changes here.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from models import Case
from routers._deps import CurrentUser, current_user, require_perm
from services.graph import get_graph_service
from services.vendor_scope import enforce_vendor_scope


router = APIRouter(
    prefix="/graph", tags=["Graph"],
    dependencies=[Depends(enforce_vendor_scope)],
)


@router.get("/stats")
@require_perm("case.read")
def graph_stats(user: CurrentUser = Depends(current_user)):
    """Sizing diagnostics — for the operator to decide when a tenant is
    big enough to warrant the Mongo-native or Neo4j backend."""
    svc = get_graph_service()
    return svc.stats(user.tenant_id)


@router.get("/cases/{case_id}/neighborhood")
@require_perm("case.read")
def case_neighborhood(
    case_id: str,
    depth: int = 2,
    min_confidence: float = 0.4,
    user: CurrentUser = Depends(current_user),
):
    """Everything connected to this case within `depth` hops."""
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    svc = get_graph_service()
    sg = svc.case_neighborhood(
        user.tenant_id, case_id,
        depth=max(1, min(depth, 4)),
        min_confidence=max(0.0, min(min_confidence, 1.0)),
    )
    return sg.to_dict()


@router.get("/persons/across-cases")
@require_perm("case.read")
def persons_across_cases(
    name: str,
    exclude_case_id: Optional[str] = None,
    min_confidence: float = 0.4,
    user: CurrentUser = Depends(current_user),
):
    if not name.strip():
        raise HTTPException(422, "`name` required")
    svc = get_graph_service()
    sg = svc.person_across_cases(
        user.tenant_id, name,
        exclude_case_id=exclude_case_id,
        min_confidence=max(0.0, min(min_confidence, 1.0)),
    )
    return sg.to_dict()


@router.get("/persons/network")
@require_perm("case.read")
def persons_network(
    name: str,
    exclude_case_id: Optional[str] = None,
    min_confidence: float = 0.4,
    user: CurrentUser = Depends(current_user),
):
    if not name.strip():
        raise HTTPException(422, "`name` required")
    svc = get_graph_service()
    sg = svc.person_network(
        user.tenant_id, name,
        exclude_case_id=exclude_case_id,
        min_confidence=max(0.0, min(min_confidence, 1.0)),
    )
    return sg.to_dict()


@router.get("/persons/path")
@require_perm("case.read")
def persons_shortest_path(
    source_person_id: str,
    target_person_id: str,
    max_hops: int = 5,
    min_confidence: float = 0.4,
    user: CurrentUser = Depends(current_user),
):
    if source_person_id == target_person_id:
        raise HTTPException(422, "source and target must differ")
    svc = get_graph_service()
    paths = svc.shortest_path_persons(
        user.tenant_id, source_person_id, target_person_id,
        max_hops=max(1, min(max_hops, 8)),
        min_confidence=max(0.0, min(min_confidence, 1.0)),
    )
    return {"paths": [p.to_dict() for p in paths]}


@router.get("/cross-case-conflicts")
@require_perm("case.read")
def cross_case_conflicts(
    min_confidence: float = 0.4,
    mine: bool = False,
    user: CurrentUser = Depends(current_user),
):
    """Persons appearing on multiple cases under DIFFERENT roles.
    `mine=true` scopes to cases where the caller is primary investigator."""
    svc = get_graph_service()
    hits = svc.cross_case_role_conflicts(
        user.tenant_id,
        min_confidence=max(0.0, min(min_confidence, 1.0)),
        primary_investigator_id=user.user_id if mine else None,
    )
    return {"hits": [h.to_dict() for h in hits]}


@router.post("/invalidate")
@require_perm("case.read")
def invalidate_cache(user: CurrentUser = Depends(current_user)):
    """Operator escape hatch — drop the in-memory cache for this tenant.
    Useful after a bulk Mongo edit done outside the API."""
    svc = get_graph_service()
    svc.invalidate(user.tenant_id)
    return {"ok": True}
