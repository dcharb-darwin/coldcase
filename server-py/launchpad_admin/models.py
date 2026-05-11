"""
MongoEngine documents for RBAC state.

Two collections, both partitioned by (tenant_id, app_id) so one DB can host
multiple apps without cross-contamination.
"""

from __future__ import annotations

from datetime import datetime

from mongoengine import (
    BooleanField,
    DateTimeField,
    Document,
    ListField,
    ReferenceField,
    StringField,
)


class Role(Document):
    """A named permission bundle, scoped to (tenant_id, app_id).

    `is_system=True` roles are seeded from the AppManifest and represent the
    app's default role templates. Tenants can modify them (when editable) or
    clone them into custom (`is_system=False`) roles.
    """

    tenant_id = StringField(required=True, max_length=100)
    app_id = StringField(required=True, max_length=64)
    name = StringField(required=True, max_length=64)
    description = StringField(default="", max_length=500)
    permissions = ListField(StringField(max_length=128))
    is_system = BooleanField(default=False)
    is_system_editable = BooleanField(default=True)
    """When False (for system roles), the role cannot be edited — only cloned."""

    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "launchpad_admin_roles",
        "indexes": [
            {"fields": ["tenant_id", "app_id", "name"], "unique": True},
            "tenant_id",
            "app_id",
        ],
    }

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "tenant_id": self.tenant_id,
            "app_id": self.app_id,
            "name": self.name,
            "description": self.description,
            "permissions": list(self.permissions or []),
            "is_system": bool(self.is_system),
            "is_system_editable": bool(self.is_system_editable),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RoleAssignment(Document):
    """Grants a user the permissions of a role within a tenant+app, optionally
    scoped to a single resource (scope_id)."""

    user_id = StringField(required=True, max_length=100)
    """Govern user id — stable across sessions."""

    tenant_id = StringField(required=True, max_length=100)
    app_id = StringField(required=True, max_length=64)
    role = ReferenceField(Role, required=True)

    scope_type = StringField(default=None, max_length=64)
    """Which ScopeType from the app manifest this assignment applies to.
    Must be either None (tenant-wide) or one of `manifest.scope_type_ids()`.
    Examples for SOP Builder: 'owner_group' or 'sop'."""

    scope_id = StringField(default=None, max_length=100)
    """Null = tenant-wide. Non-null = the specific resource instance id (paired
    with scope_type). E.g., owner_group_id, or an individual sop_id."""

    granted_by = StringField(default="", max_length=100)
    granted_at = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "launchpad_admin_role_assignments",
        "indexes": [
            {"fields": ["user_id", "tenant_id", "app_id"]},
            {"fields": ["tenant_id", "app_id"]},
            "role",
        ],
    }

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "app_id": self.app_id,
            "role_id": str(self.role.id) if self.role else None,
            "role_name": self.role.name if self.role else None,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
        }


class RoleMapping(Document):
    """Auto-assignment rule: users matching an identity attribute receive a role.

    Examples:
        - Every user in AD group "HR-Managers" gets role `library_editor`
          scoped to owner_group=<HR library id>.
        - Every user whose Govern `department` claim is "IT" gets role
          `library_editor` scoped to owner_group=<IT library id>.

    These are evaluated **per-request** by the middleware — no per-user DB
    rows. A change to a mapping reflects immediately for every matching user
    on their next request. Direct RoleAssignment rows can be used alongside
    for individual overrides.
    """

    tenant_id = StringField(required=True, max_length=100)
    app_id = StringField(required=True, max_length=64)

    match_type = StringField(required=True, max_length=32, choices=["ad_group", "department"])
    """Which claim to match against. "ad_group" reads UserContext.govern_roles;
    "department" reads UserContext.attributes['department']."""

    match_value = StringField(required=True, max_length=200)
    """Exact-match value. Case-sensitive today; normalize upstream if needed."""

    role = ReferenceField(Role, required=True)
    scope_type = StringField(default=None, max_length=64)
    scope_id = StringField(default=None, max_length=100)

    notes = StringField(default="", max_length=500)
    created_at = DateTimeField(default=datetime.utcnow)
    created_by = StringField(default="", max_length=100)

    meta = {
        "collection": "launchpad_admin_role_mappings",
        "indexes": [
            {"fields": ["tenant_id", "app_id", "match_type"]},
            {"fields": ["tenant_id", "app_id", "match_type", "match_value"]},
        ],
    }

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "tenant_id": self.tenant_id,
            "app_id": self.app_id,
            "match_type": self.match_type,
            "match_value": self.match_value,
            "role_id": str(self.role.id) if self.role else None,
            "role_name": self.role.name if self.role else None,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }
