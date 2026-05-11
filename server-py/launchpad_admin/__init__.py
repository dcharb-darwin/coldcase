"""
darwin-launchpad-admin — shared RBAC building blocks for Launchpad apps.

This package is meant to be dropped into any Darwin Launchpad app and wired
per the INTEGRATION_GUIDE. See ADR-001 for the architecture rationale.

Public surface:
    - manifest.AppManifest, PermissionMeta, SeedRole
    - context.UserContext
    - decorators.require_permission, require_sa
    - middleware.user_context_middleware, get_user_context
    - seed.seed_system_roles
    - router.build_admin_router
"""

from .manifest import AppManifest, PermissionMeta, SeedRole
from .context import UserContext
from .decorators import require_permission, require_sa
from .middleware import user_context_middleware, get_user_context
from .seed import seed_system_roles
from .router import build_admin_router

__all__ = [
    "AppManifest",
    "PermissionMeta",
    "SeedRole",
    "UserContext",
    "require_permission",
    "require_sa",
    "user_context_middleware",
    "get_user_context",
    "seed_system_roles",
    "build_admin_router",
]

__version__ = "0.1.0"
