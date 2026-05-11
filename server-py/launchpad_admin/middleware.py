"""
Request middleware + FastAPI dependency for UserContext resolution.

The middleware reads the Govern token (or dev-bypass shim), looks up the
user's RoleAssignments for the current app+tenant, and assembles a
UserContext which it attaches to `request.state.user_context`.

Handlers get at it via:
    async def handler(ctx: UserContext = Depends(get_user_context)):
"""

from __future__ import annotations

from typing import Callable

from fastapi import HTTPException, Request, status

from .context import UserContext
from .models import Role, RoleAssignment, RoleMapping


# Apps override this by monkey-patching or by subclassing the middleware.
# Default implementation reads the dev bypass stub — swap for real Govern
# integration in production.
async def resolve_identity_from_request(request: Request) -> dict:
    """Returns raw identity claims. Override for real Govern integration.

    Expected shape:
        {
            "user_id": str,
            "email": str,
            "first_name": str,
            "last_name": str,
            "tenant_id": str,
            "tenant_name": str,
            "is_super_admin": bool,
            "govern_roles": list[str],
            "attributes": dict,
        }
    """
    # Default: try to import the app's dev bypass. Real deployments override.
    try:
        import os
        from core.dev_auth_bypass import DEV_USER_ID, DEV_TENANT_ID  # type: ignore

        # Simulate AD groups + department claims locally for testing mappings.
        # Comma-separated list; unset = no groups (same as today).
        dev_groups = [g.strip() for g in os.environ.get("DEV_AD_GROUPS", "").split(",") if g.strip()]
        dev_department = os.environ.get("DEV_DEPARTMENT", "") or None
        # DEV_SA=0 lets you test non-SA flows (forces the permission check path).
        is_sa = os.environ.get("DEV_SA", "1") != "0"
        return {
            "user_id": DEV_USER_ID,
            "email": "dev@localhost",
            "first_name": "Dev",
            "last_name": "User",
            "tenant_id": DEV_TENANT_ID,
            "tenant_name": "Dev Tenant",
            "is_super_admin": is_sa,
            "govern_roles": dev_groups,
            "attributes": {"department": dev_department} if dev_department else {},
        }
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No identity resolver configured",
        )


# The app_id the middleware uses when looking up role assignments.
# Set once at startup by `build_admin_router` or by calling `configure(app_id=...)`.
_APP_ID: str | None = None


def configure(app_id: str) -> None:
    """Bind the middleware to a specific app_id. Called by build_admin_router."""
    global _APP_ID
    _APP_ID = app_id


def _load_effective_permissions(
    user_id: str,
    tenant_id: str,
    app_id: str,
    govern_roles: list[str] | None = None,
    attributes: dict | None = None,
) -> tuple[set[str], dict[str, set[str]], list[str]]:
    """Compute the user's effective permissions = direct assignments ∪ mappings.

    - tenant-wide permissions (scope_id=None)
    - scoped permissions (keyed by `"<scope_type>:<scope_id>"`)
    - role names (for display — direct + mapping-derived)

    Mappings are evaluated per-request against the user's Govern claims
    (AD groups, department) so changes to mappings take effect immediately
    for every matching user.
    """
    tenant_wide: set[str] = set()
    scoped: dict[str, set[str]] = {}
    role_names: list[str] = []

    def apply_role_grant(role: Role, scope_type: str | None, scope_id: str | None, source: str) -> None:
        """Union one role's permissions into the running totals."""
        if not role:
            return
        perms = set(role.permissions or [])
        role_names.append(role.name if source == "direct" else f"{role.name} (via {source})")
        if scope_id is None:
            tenant_wide.update(perms)
        else:
            stype = scope_type or ""
            key = f"{stype}:{scope_id}"
            scoped.setdefault(key, set()).update(perms)

    # ── 1. Direct RoleAssignments ─────────────────────────────────────────
    for assignment in RoleAssignment.objects(user_id=user_id, tenant_id=tenant_id, app_id=app_id):
        apply_role_grant(assignment.role, assignment.scope_type, assignment.scope_id, "direct")

    # ── 2. Mapping-derived roles (per-request, no DB write) ───────────────
    groups = set(govern_roles or [])
    department = (attributes or {}).get("department")

    if groups or department:
        mappings = RoleMapping.objects(tenant_id=tenant_id, app_id=app_id)
        for m in mappings:
            matches = False
            if m.match_type == "ad_group" and m.match_value in groups:
                matches = True
                src = f"AD: {m.match_value}"
            elif m.match_type == "department" and department == m.match_value:
                matches = True
                src = f"dept: {m.match_value}"
            if matches:
                apply_role_grant(m.role, m.scope_type, m.scope_id, src)

    return tenant_wide, scoped, role_names


async def user_context_middleware(request: Request, call_next: Callable):
    """ASGI middleware — attaches UserContext to request.state for each request.

    Skips unauthenticated routes by letting resolve_identity_from_request raise;
    the exception handler returns 401 upstream.
    """
    # Short-circuit health-check endpoints — they shouldn't require auth.
    if request.url.path in ("/live", "/health", "/ready"):
        return await call_next(request)

    try:
        claims = await resolve_identity_from_request(request)
    except HTTPException:
        # Let the handler decide whether auth was required for this route.
        request.state.user_context = None
        return await call_next(request)

    app_id = _APP_ID or "unknown"

    # ── SA-only impersonation ────────────────────────────────────────────
    # Header-based: the frontend sets X-Impersonate-User-Id on every
    # request while the SA is "seeing as" another user. Non-SA tokens that
    # send the header are silently ignored — impersonation is never a
    # permission, only the Govern SA bypass qualifies.
    real_is_sa = bool(claims.get("is_super_admin", False))
    impersonate_target = request.headers.get("x-impersonate-user-id", "").strip()
    impersonating = bool(impersonate_target) and real_is_sa
    impersonator_user_id: str | None = None
    impersonator_email = ""

    if impersonating:
        impersonator_user_id = claims["user_id"]
        impersonator_email = claims.get("email", "")
        # Swap the user_id + clear SA flag. We don't have a way to look up
        # the target's Govern claims from here (department, AD groups), so
        # mapping-derived roles won't fire — that's a known limitation we
        # document in the UI. Direct RoleAssignments evaluate fully.
        claims = {
            **claims,
            "user_id": impersonate_target,
            "email": f"(impersonated:{impersonate_target})",
            "first_name": "",
            "last_name": "",
            "is_super_admin": False,
            "govern_roles": [],
            "attributes": {},
        }

    perms, scoped, role_names = _load_effective_permissions(
        claims["user_id"],
        claims["tenant_id"],
        app_id,
        govern_roles=claims.get("govern_roles", []),
        attributes=claims.get("attributes", {}),
    )

    ctx = UserContext(
        user_id=claims["user_id"],
        email=claims["email"],
        first_name=claims.get("first_name", ""),
        last_name=claims.get("last_name", ""),
        tenant_id=claims["tenant_id"],
        tenant_name=claims.get("tenant_name", ""),
        is_super_admin=bool(claims.get("is_super_admin", False)),
        govern_roles=claims.get("govern_roles", []),
        attributes=claims.get("attributes", {}),
        permissions=perms,
        scoped_permissions=scoped,
        role_names=role_names,
        impersonator_user_id=impersonator_user_id,
        impersonator_email=impersonator_email,
    )
    request.state.user_context = ctx
    return await call_next(request)


def get_user_context(request: Request) -> UserContext:
    """FastAPI dependency. Raises 401 if no context is attached."""
    ctx = getattr(request.state, "user_context", None)
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return ctx
