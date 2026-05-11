"""
AppManifest — the per-app declaration of permissions, seed roles, and scope types.

Every Launchpad app ships one of these (typically at `auth/app_manifest.py`).
The framework reads it to:
- Seed system roles on first boot
- Validate custom-role permissions against the catalog
- Render the role editor's checkbox grid
- Drive backend permission checks
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class PermissionMeta:
    """UI metadata for a permission. The permission's identity is its string
    key in `AppManifest.permissions`; this struct only describes how to render it.

    Labels should read as **capabilities**, not as permission names:
        good: "View any SOP"   /   "Create SOPs from recordings"
        bad:  "sop.read"       /   "Read SOPs"

    The tech string (the dict key) only shows in an "Advanced" drawer of the UI;
    regular admins interact with the sentence.
    """

    label: str
    """Action-oriented sentence shown in the role editor."""

    description: str = ""
    """Optional longer explanation shown as a tooltip or inline help."""

    group: str = "General"
    """Group heading in the role editor's checkbox grid."""


@dataclass(frozen=True)
class ScopeType:
    """A resource type that role assignments can be scoped to.

    Example for SOP Builder:
        ScopeType(id="owner_group", label="Library",
                  list_endpoint="/owner-groups/")
        ScopeType(id="sop", label="Individual SOP",
                  list_endpoint="/sops/")

    A RoleAssignment with no scope is tenant-wide. With a scope set, the
    assignment applies only to that specific resource instance. Multiple
    scope types per app let a single role (e.g. `reader`) be granted at
    library level or at an individual-SOP level without needing separate roles.
    """

    id: str
    """Stable identifier used in RoleAssignment.scope_type. Never rename."""

    label: str
    """Display label for the scope type in the assignment picker."""

    description: str = ""
    list_endpoint: str | None = None
    """Optional API path the admin UI can call to fetch candidate scope ids."""


@dataclass(frozen=True)
class SeedRole:
    """A role shipped by the app, seeded into each tenant's DB on first boot.

    Tenants can edit seed roles (adding/removing permissions) when
    `editable=True`, and clone them into custom roles regardless of `editable`.
    """

    permissions: list[str]
    """Permission strings, or `["*"]` for "all permissions in the manifest"."""

    description: str = ""
    editable: bool = True
    """When False, tenants cannot modify this role directly — only clone it.
    Typically False for the `admin` role to prevent accidental lockout."""


@dataclass(frozen=True)
class AppManifest:
    """The complete admin configuration for one Launchpad app."""

    app_id: str
    """Stable slug partitioning roles/assignments per app. Never change after seeding."""

    display_name: str
    """Human-readable app name used in the admin UI."""

    permissions: Mapping[str, PermissionMeta]
    """The full permission catalog. Permission strings are immutable vocabulary;
    they only exist because some endpoint or UI element checks them."""

    seed_roles: Mapping[str, SeedRole]
    """System roles seeded into each tenant's DB. Key = role name."""

    app_identity: str = ""
    """A plain-English paragraph the AI assistant uses to understand the
    app's domain: what resources exist, what terms mean, what the
    permission vocabulary is really for. The LLM reads this before
    proposing actions — the richer and more opinionated, the better the
    proposals. Safe to include nomenclature aliases (e.g. "'library' and
    'owner_group' are the same concept"). Keep under ~300 words."""

    scope_types: list[ScopeType] = field(default_factory=list)
    """Resource types available as scope for role assignments. Empty = tenant-
    wide-only assignments. Multiple types allow an assignment to be scoped at
    different granularities (e.g., one assignment at library level, another at
    individual SOP level)."""

    # ── Legacy single-scope fields (kept for back-compat with older manifests) ──
    scope_type: str | None = None
    """DEPRECATED: use `scope_types` instead. If set, promoted into scope_types
    automatically for manifests that haven't migrated yet."""

    scope_list_endpoint: str | None = None
    """DEPRECATED companion to `scope_type`."""

    def __post_init__(self) -> None:
        # Back-compat: promote legacy scope_type → scope_types.
        if self.scope_type and not self.scope_types:
            # `frozen=True` dataclasses need object.__setattr__ here.
            object.__setattr__(
                self,
                "scope_types",
                [
                    ScopeType(
                        id=self.scope_type,
                        label=self.scope_type.replace("_", " ").title(),
                        list_endpoint=self.scope_list_endpoint,
                    )
                ],
            )

    def resolve_permissions(self, role: SeedRole) -> list[str]:
        """Expand `["*"]` to the full permission set; pass-through otherwise."""
        if role.permissions == ["*"]:
            return list(self.permissions.keys())
        return list(role.permissions)

    def validate_permissions(self, perms: list[str]) -> list[str]:
        """Return any permissions not present in the catalog.
        Used when accepting custom roles to reject unknown permission strings."""
        catalog = set(self.permissions.keys())
        return [p for p in perms if p not in catalog]

    def scope_type_ids(self) -> set[str]:
        return {st.id for st in self.scope_types}
