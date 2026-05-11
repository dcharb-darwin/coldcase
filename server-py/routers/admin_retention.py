"""F22 — Retention sweep admin endpoint.

Dry-run (`apply=false`) returns the inspection plan without deletion;
`apply=true` actually purges. Either way, the first-AI-draft floor is
enforced (rule #10 / §13663(b)) and PURGE_BLOCKED events are emitted.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from routers._deps import CurrentUser, current_user, require_perm
from services import retention_sweeper


router = APIRouter(prefix="/admin/retention", tags=["Retention"])


@router.post("/sweep")
@require_perm("retention.manage")
def run_retention_sweep(
    apply: bool = Query(False, description="If false (default), runs in dry-run mode and reports what would be purged."),
    user: CurrentUser = Depends(current_user),
):
    report = retention_sweeper.sweep(
        tenant_id=user.tenant_id,
        apply=apply,
        actor_user_id=user.user_id,
        actor_display=user.display_name,
    )
    return retention_sweeper.to_dict(report)
