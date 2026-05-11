"""
Seed system roles into the DB from an AppManifest. Idempotent — safe to run
on every startup.

Called once at app startup:

    from launchpad_admin.seed import seed_system_roles
    from auth.app_manifest import APP_MANIFEST

    @app.on_event("startup")
    async def on_startup():
        seed_system_roles(APP_MANIFEST)

Seeding behavior:
    - Creates missing system roles with permissions from the manifest.
    - If a system role already exists and `is_system_editable=False`, its
      permissions are overwritten to match the manifest (we trust the manifest
      as the locked source of truth for non-editable roles).
    - If a system role already exists and `is_system_editable=True`, its
      permissions are left alone — the tenant may have tuned it, don't clobber.
    - Never touches custom (is_system=False) roles.

Multi-tenant note: seeding is per-tenant. This function seeds for one tenant
at a time. Call it from your tenant-provisioning flow, and also once on
startup for the "dev tenant" in local POCs.
"""

from __future__ import annotations

import logging

from .manifest import AppManifest
from .models import Role

logger = logging.getLogger(__name__)


def seed_system_roles(manifest: AppManifest, tenant_id: str) -> dict:
    """Ensure the manifest's system roles exist for `tenant_id`.

    Returns a summary dict: {role_name: "created" | "updated" | "unchanged"}.
    """
    summary: dict[str, str] = {}

    for role_name, seed in manifest.seed_roles.items():
        resolved_perms = manifest.resolve_permissions(seed)

        existing: Role | None = Role.objects(
            tenant_id=tenant_id, app_id=manifest.app_id, name=role_name
        ).first()

        if existing is None:
            Role(
                tenant_id=tenant_id,
                app_id=manifest.app_id,
                name=role_name,
                description=seed.description,
                permissions=resolved_perms,
                is_system=True,
                is_system_editable=seed.editable,
            ).save()
            summary[role_name] = "created"
            logger.info(
                "Seeded system role: app=%s tenant=%s role=%s",
                manifest.app_id,
                tenant_id,
                role_name,
            )
            continue

        # Exists — update only if locked (editable=False). Otherwise respect
        # any tenant tuning.
        if not existing.is_system_editable:
            if list(existing.permissions or []) != resolved_perms or \
               existing.is_system_editable != seed.editable:
                existing.permissions = resolved_perms
                existing.description = seed.description or existing.description
                existing.is_system_editable = seed.editable
                existing.save()
                summary[role_name] = "updated"
            else:
                summary[role_name] = "unchanged"
        else:
            summary[role_name] = "unchanged"

    return summary
