"""
UserContext — the authenticated user, resolved per-request.

Assembled by `middleware.user_context_middleware` from:
- Govern Platform token claims (identity + is_super_admin)
- Per-app DB RoleAssignments (effective permissions)

Handlers receive this via the `get_user_context` FastAPI dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UserContext:
    """The authenticated user plus their effective permissions in the current app+tenant."""

    user_id: str
    email: str
    first_name: str
    last_name: str
    tenant_id: str
    tenant_name: str = ""
    is_super_admin: bool = False
    """True when Govern claims the user is SA; bypasses every permission check."""

    govern_roles: list[str] = field(default_factory=list)
    """Cross-app roles from Govern (e.g., AD groups). Informational only — the
    framework doesn't use these for permission decisions; apps may."""

    attributes: dict = field(default_factory=dict)
    """Free-form claims from Govern (department, etc). App-specific use."""

    # Computed per-request by the middleware:
    permissions: set[str] = field(default_factory=set)
    """Union of permissions from all tenant-wide RoleAssignments."""

    scoped_permissions: dict[str, set[str]] = field(default_factory=dict)
    """Permissions granted only within a specific scope. Keyed by composite
    strings `"<scope_type>:<scope_id>"` (e.g., `"owner_group:abc123"` or
    `"sop:ff00..."`)."""

    role_names: list[str] = field(default_factory=list)
    """Role names this user holds (for display/audit — not for permission checks)."""

    # ── Impersonation (SA-only, see middleware) ───────────────────────────
    impersonator_user_id: str | None = None
    """When set, every field above describes the impersonated target user;
    this field records the SA who initiated the impersonation. Write audits
    should include this so actions-as-someone-else are traceable."""

    impersonator_email: str = ""

    def can(
        self,
        permission: str,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> bool:
        """Single source of truth for permission decisions.

        Order of checks:
          1. SA bypass
          2. Tenant-wide grants
          3. Scoped grant for (scope_type, scope_id), if both given

        Passing scope_id without scope_type is permitted for callers that
        don't know which type applies — it matches across every scope_type.
        For deliberate per-type checks pass both.
        """
        if self.is_super_admin:
            return True
        if permission in self.permissions:
            return True
        if scope_id:
            if scope_type:
                key = f"{scope_type}:{scope_id}"
                if permission in self.scoped_permissions.get(key, set()):
                    return True
            else:
                for key, perms in self.scoped_permissions.items():
                    if key.endswith(f":{scope_id}") and permission in perms:
                        return True
        return False

    def has_role(self, role_name: str) -> bool:
        return role_name in self.role_names
