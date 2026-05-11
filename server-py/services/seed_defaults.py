"""Seed default domain data for local dev + first-boot.

Idempotent. Only seeds what cold case needs:
  - dev-user admin role assignment so the Admin panel is usable locally.
  - a single demo case so the UI has something to render on first boot.

Domain-specific seeders for documents / conversations / reports are deliberately
omitted — those are synthetic data that should ship in `seed/` under a separate
script, not run on every startup.
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def seed_dev_admin_assignment(tenant_id: str, user_id: str, app_id: str) -> bool:
    """Grant dev user the `admin` role in dev tenant so the Admin panel works
    locally. Safe no-op in production: the dev user id doesn't exist there."""
    from launchpad_admin.models import Role, RoleAssignment

    admin_role = Role.objects(
        tenant_id=tenant_id, app_id=app_id, name="admin"
    ).first()
    if not admin_role:
        logger.warning(
            "Cannot seed dev admin assignment: 'admin' role not found "
            "(did system role seed run?)"
        )
        return False

    existing = RoleAssignment.objects(
        user_id=user_id, tenant_id=tenant_id, app_id=app_id,
        role=admin_role, scope_id=None,
    ).first()
    if existing:
        return False

    RoleAssignment(
        user_id=user_id, tenant_id=tenant_id, app_id=app_id,
        role=admin_role, scope_id=None, granted_by="seed",
    ).save()
    logger.info("Seeded admin RoleAssignment for dev user %s", user_id)
    return True


def seed_demo_case(tenant_id: str, user_id: str) -> bool:
    """A single demo case so the frontend has something on first boot."""
    from models import Case

    if Case.objects(tenant_id=tenant_id).first():
        return False
    Case(
        tenant_id=tenant_id,
        case_number="CC-2026-0001",
        title="Demo cold case — replace with real data",
        classification="other",
        retention_policy="match_official_report",
        primary_investigator_id=user_id,
        created_by=user_id,
        description=(
            "This is a placeholder case created by `seed_defaults.seed_demo_case`. "
            "Delete it once you have real cases registered."
        ),
    ).save()
    logger.info("Seeded demo Case CC-2026-0001 for tenant %s", tenant_id)
    return True


def seed_all(tenant_id: str, dev_user_id: str, app_id: str) -> dict:
    return {
        "dev_admin_assignment_created": seed_dev_admin_assignment(
            tenant_id, dev_user_id, app_id
        ),
        "demo_case_created": seed_demo_case(tenant_id, dev_user_id),
    }
