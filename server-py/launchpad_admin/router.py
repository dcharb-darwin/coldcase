"""
Admin router factory — builds a FastAPI APIRouter bound to a specific AppManifest.

Mounted by each app:

    app.include_router(build_admin_router(APP_MANIFEST), prefix="/admin")

Exposes:
    GET    /admin/manifest               Public within the app — returns the permission
                                         catalog and seed-role definitions for UI render
    GET    /admin/me                     Current user's context + effective permissions
    GET    /admin/roles                  List roles in the caller's tenant
    POST   /admin/roles                  Create a custom role           [roles.manage]
    GET    /admin/roles/{id}             Get one role
    PUT    /admin/roles/{id}             Edit a role (guarded)           [roles.manage]
    DELETE /admin/roles/{id}             Delete a custom role            [roles.manage]
    POST   /admin/roles/{id}/reset       Reset a system role to manifest defaults
                                                                         [roles.manage]
    POST   /admin/roles/{id}/clone       Clone into a new custom role    [roles.manage]
    GET    /admin/assignments            List assignments in tenant      [roles.manage]
    POST   /admin/assignments            Assign a role to a user         [roles.manage]
    DELETE /admin/assignments/{id}       Revoke                          [roles.manage]
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .context import UserContext
from .decorators import require_permission
from .manifest import AppManifest
from .middleware import configure as configure_middleware
from .middleware import get_user_context
from .models import Role, RoleAssignment, RoleMapping


# ── Request bodies ──────────────────────────────────────────────────────────


class RoleCreateRequest(BaseModel):
    name: str
    description: str = ""
    permissions: list[str]


class RoleUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None


class RoleCloneRequest(BaseModel):
    new_name: str
    description: str = ""


class AssignmentCreateRequest(BaseModel):
    user_id: str
    role_id: str
    scope_type: str | None = None
    scope_id: str | None = None


class MappingCreateRequest(BaseModel):
    match_type: str                     # "ad_group" | "department"
    match_value: str
    role_id: str
    scope_type: str | None = None
    scope_id: str | None = None
    notes: str = ""


class AssistRequest(BaseModel):
    prompt: str


class ImpersonateRequest(BaseModel):
    target_user_id: str


# ── Router factory ──────────────────────────────────────────────────────────


def build_admin_router(manifest: AppManifest) -> APIRouter:
    """Build a FastAPI router bound to `manifest`. Mount at /admin."""
    configure_middleware(app_id=manifest.app_id)
    router = APIRouter()

    # ─── Manifest introspection ──────────────────────────────────────────

    @router.get("/manifest")
    async def get_manifest(ctx: UserContext = Depends(get_user_context)):
        """Returns the app's permission catalog + seed role definitions for
        UI rendering. Auth required but no permission gate — every signed-in
        user needs to know what the available permissions mean (for rendering
        their own 'My Access' view)."""
        return {
            "app_id": manifest.app_id,
            "display_name": manifest.display_name,
            # Legacy fields — clients that haven't migrated still read these.
            "scope_type": manifest.scope_type or (manifest.scope_types[0].id if manifest.scope_types else None),
            "scope_list_endpoint": manifest.scope_list_endpoint,
            # Canonical list — the new UI reads this.
            "scope_types": [
                {
                    "id": st.id,
                    "label": st.label,
                    "description": st.description,
                    "list_endpoint": st.list_endpoint,
                }
                for st in manifest.scope_types
            ],
            "permissions": {
                perm: {
                    "label": meta.label,
                    "description": meta.description,
                    "group": meta.group,
                }
                for perm, meta in manifest.permissions.items()
            },
            "seed_roles": {
                name: {
                    "permissions": manifest.resolve_permissions(seed),
                    "description": seed.description,
                    "editable": seed.editable,
                }
                for name, seed in manifest.seed_roles.items()
            },
        }

    @router.get("/me")
    async def me(ctx: UserContext = Depends(get_user_context)):
        """Current user's identity + effective permissions for this app+tenant."""
        return {
            "user_id": ctx.user_id,
            "email": ctx.email,
            "first_name": ctx.first_name,
            "last_name": ctx.last_name,
            "tenant_id": ctx.tenant_id,
            "tenant_name": ctx.tenant_name,
            "is_super_admin": ctx.is_super_admin,
            "permissions": sorted(ctx.permissions),
            "scoped_permissions": {
                scope_id: sorted(perms)
                for scope_id, perms in ctx.scoped_permissions.items()
            },
            "roles": ctx.role_names,
            # Useful for debugging mappings: "I'm in these AD groups; which
            # mappings should be firing?"
            "govern_roles": ctx.govern_roles,
            "attributes": ctx.attributes,
            # Impersonation state (null when not active) — the UI uses this
            # to render the "🎭 Impersonating" banner.
            "impersonator_user_id": ctx.impersonator_user_id,
            "impersonator_email": ctx.impersonator_email,
        }

    # ─── Roles ────────────────────────────────────────────────────────────

    @router.get("/roles")
    async def list_roles(ctx: UserContext = Depends(get_user_context)):
        """Every signed-in user may read roles (for the role picker on their
        own profile or 'My Access'). Managing requires `roles.manage`."""
        roles = Role.objects(tenant_id=ctx.tenant_id, app_id=manifest.app_id).order_by(
            "-is_system", "name"
        )
        return [r.to_dict() for r in roles]

    @router.post("/roles")
    @require_permission("roles.manage")
    async def create_role(
        data: RoleCreateRequest, ctx: UserContext = Depends(get_user_context)
    ):
        unknown = manifest.validate_permissions(data.permissions)
        if unknown:
            raise HTTPException(400, f"Unknown permissions: {unknown}")
        _assert_no_escalation(ctx, data.permissions)
        if Role.objects(
            tenant_id=ctx.tenant_id, app_id=manifest.app_id, name=data.name
        ).first():
            raise HTTPException(409, f"Role '{data.name}' already exists")

        role = Role(
            tenant_id=ctx.tenant_id,
            app_id=manifest.app_id,
            name=data.name,
            description=data.description,
            permissions=data.permissions,
            is_system=False,
            is_system_editable=True,
        ).save()
        return role.to_dict()

    @router.get("/roles/{role_id}")
    async def get_role(role_id: str, ctx: UserContext = Depends(get_user_context)):
        role = _get_role_or_404(role_id, ctx, manifest)
        return role.to_dict()

    @router.put("/roles/{role_id}")
    @require_permission("roles.manage")
    async def update_role(
        role_id: str,
        data: RoleUpdateRequest,
        ctx: UserContext = Depends(get_user_context),
    ):
        role = _get_role_or_404(role_id, ctx, manifest)
        if role.is_system and not role.is_system_editable:
            raise HTTPException(
                400, "This system role is locked. Clone it to customize."
            )
        if data.permissions is not None:
            unknown = manifest.validate_permissions(data.permissions)
            if unknown:
                raise HTTPException(400, f"Unknown permissions: {unknown}")
            _assert_no_escalation(ctx, data.permissions)
            role.permissions = data.permissions
        if data.name is not None:
            role.name = data.name
        if data.description is not None:
            role.description = data.description
        role.updated_at = datetime.utcnow()
        role.save()
        return role.to_dict()

    @router.delete("/roles/{role_id}")
    @require_permission("roles.manage")
    async def delete_role(
        role_id: str, ctx: UserContext = Depends(get_user_context)
    ):
        role = _get_role_or_404(role_id, ctx, manifest)
        if role.is_system:
            raise HTTPException(400, "System roles cannot be deleted. Edit or reset instead.")
        assigned_count = RoleAssignment.objects(role=role).count()
        if assigned_count > 0:
            raise HTTPException(
                409,
                f"Role has {assigned_count} assignment(s). Revoke them before deleting.",
            )
        role.delete()
        return {"deleted": role_id}

    @router.post("/roles/{role_id}/reset")
    @require_permission("roles.manage")
    async def reset_role(
        role_id: str, ctx: UserContext = Depends(get_user_context)
    ):
        """Restore a system role's permissions to the manifest defaults."""
        role = _get_role_or_404(role_id, ctx, manifest)
        if not role.is_system:
            raise HTTPException(400, "Reset only applies to system roles")
        seed = manifest.seed_roles.get(role.name)
        if not seed:
            raise HTTPException(404, "No manifest definition for this role")
        role.permissions = manifest.resolve_permissions(seed)
        role.description = seed.description
        role.updated_at = datetime.utcnow()
        role.save()
        return role.to_dict()

    @router.post("/roles/{role_id}/clone")
    @require_permission("roles.manage")
    async def clone_role(
        role_id: str,
        data: RoleCloneRequest,
        ctx: UserContext = Depends(get_user_context),
    ):
        source = _get_role_or_404(role_id, ctx, manifest)
        if Role.objects(
            tenant_id=ctx.tenant_id, app_id=manifest.app_id, name=data.new_name
        ).first():
            raise HTTPException(409, f"Role '{data.new_name}' already exists")
        _assert_no_escalation(ctx, list(source.permissions or []))
        clone = Role(
            tenant_id=ctx.tenant_id,
            app_id=manifest.app_id,
            name=data.new_name,
            description=data.description or f"Cloned from {source.name}",
            permissions=list(source.permissions or []),
            is_system=False,
            is_system_editable=True,
        ).save()
        return clone.to_dict()

    # ─── Assignments ──────────────────────────────────────────────────────

    @router.get("/assignments")
    @require_permission("roles.manage")
    async def list_assignments(ctx: UserContext = Depends(get_user_context)):
        rows = RoleAssignment.objects(
            tenant_id=ctx.tenant_id, app_id=manifest.app_id
        )
        return [r.to_dict() for r in rows]

    @router.post("/assignments")
    @require_permission("roles.manage")
    async def create_assignment(
        data: AssignmentCreateRequest, ctx: UserContext = Depends(get_user_context)
    ):
        role = Role.objects(
            id=data.role_id, tenant_id=ctx.tenant_id, app_id=manifest.app_id
        ).first()
        if not role:
            raise HTTPException(404, "Role not found in this tenant/app")
        _assert_no_escalation(ctx, list(role.permissions or []))

        # Validate scope pairing against manifest.scope_types.
        scope_type = data.scope_type or None
        scope_id = data.scope_id or None
        if scope_id and not scope_type and manifest.scope_types:
            # Missing type but id given — fall back to the app's default.
            scope_type = manifest.scope_types[0].id
        if scope_type and scope_type not in manifest.scope_type_ids():
            raise HTTPException(
                400, f"Unknown scope_type '{scope_type}' for app {manifest.app_id}"
            )
        if scope_type and not scope_id:
            raise HTTPException(400, "scope_type set but scope_id missing")

        # Idempotent — same (user, role, scope_type, scope_id) is a no-op.
        existing = RoleAssignment.objects(
            user_id=data.user_id,
            tenant_id=ctx.tenant_id,
            app_id=manifest.app_id,
            role=role,
            scope_type=scope_type,
            scope_id=scope_id,
        ).first()
        if existing:
            return existing.to_dict()

        assignment = RoleAssignment(
            user_id=data.user_id,
            tenant_id=ctx.tenant_id,
            app_id=manifest.app_id,
            role=role,
            scope_type=scope_type,
            scope_id=scope_id,
            granted_by=ctx.user_id,
        ).save()
        return assignment.to_dict()

    @router.delete("/assignments/{assignment_id}")
    @require_permission("roles.manage")
    async def delete_assignment(
        assignment_id: str, ctx: UserContext = Depends(get_user_context)
    ):
        row = RoleAssignment.objects(
            id=assignment_id, tenant_id=ctx.tenant_id, app_id=manifest.app_id
        ).first()
        if not row:
            raise HTTPException(404, "Assignment not found")
        row.delete()
        return {"deleted": assignment_id}

    # ─── Impersonation audit markers ─────────────────────────────────────
    # The actual swap is header-driven in the middleware; these endpoints
    # exist so the UI can record an audit trail whenever an SA starts or
    # stops impersonating, and so non-SA callers who try to start get 403.
    # NOTE: ImpersonateRequest must be a module-level class (declared above)
    # so FastAPI's body-vs-query introspection works. Nested definitions
    # inside this factory silently degrade to query-string params.

    @router.post("/impersonate/start")
    async def impersonate_start(
        data: ImpersonateRequest, ctx: UserContext = Depends(get_user_context)
    ):
        # The caller's ctx here reflects the pre-impersonation identity
        # (no header set yet), so gating on is_super_admin is correct.
        if not ctx.is_super_admin:
            raise HTTPException(403, "Only Super Admins can impersonate")
        target = data.target_user_id.strip()
        if not target:
            raise HTTPException(400, "target_user_id is required")

        try:
            from services.audit import AuditAction, EntityType, record as audit_record
            audit_record(
                {"id": ctx.user_id}, AuditAction.IMPERSONATE_START, EntityType.SETTING,
                entity_id=target,
                message=f"SA {ctx.email or ctx.user_id} started impersonating {target}",
            )
        except Exception:  # audit is best-effort
            pass
        return {"impersonating": target, "sa_user_id": ctx.user_id}

    @router.post("/impersonate/stop")
    async def impersonate_stop(ctx: UserContext = Depends(get_user_context)):
        # When the frontend calls this, it's still sending the header, so
        # ctx here is the impersonated user; ctx.impersonator_user_id tells
        # us who the real SA is.
        if not ctx.impersonator_user_id:
            return {"was_impersonating": False}
        try:
            from services.audit import AuditAction, EntityType, record as audit_record
            audit_record(
                {"id": ctx.impersonator_user_id}, AuditAction.IMPERSONATE_END, EntityType.SETTING,
                entity_id=ctx.user_id,
                message=f"SA {ctx.impersonator_email or ctx.impersonator_user_id} stopped impersonating {ctx.user_id}",
            )
        except Exception:
            pass
        return {
            "was_impersonating": True,
            "target_user_id": ctx.user_id,
            "sa_user_id": ctx.impersonator_user_id,
        }

    # ─── Mappings (AD group / department → role) ─────────────────────────
    # Evaluated per-request in the middleware; changes take effect on the
    # next request for every matching user (no rewrite of assignment rows).

    @router.get("/mappings")
    @require_permission("roles.manage")
    async def list_mappings(ctx: UserContext = Depends(get_user_context)):
        rows = RoleMapping.objects(tenant_id=ctx.tenant_id, app_id=manifest.app_id)
        return [m.to_dict() for m in rows]

    @router.post("/mappings")
    @require_permission("roles.manage")
    async def create_mapping(
        data: MappingCreateRequest, ctx: UserContext = Depends(get_user_context)
    ):
        if data.match_type not in ("ad_group", "department"):
            raise HTTPException(400, "match_type must be 'ad_group' or 'department'")
        if not data.match_value.strip():
            raise HTTPException(400, "match_value is required")

        role = Role.objects(
            id=data.role_id, tenant_id=ctx.tenant_id, app_id=manifest.app_id
        ).first()
        if not role:
            raise HTTPException(404, "Role not found in this tenant/app")
        _assert_no_escalation(ctx, list(role.permissions or []))

        # Validate scope pairing.
        scope_type = data.scope_type or None
        scope_id = data.scope_id or None
        if scope_type and scope_type not in manifest.scope_type_ids():
            raise HTTPException(400, f"Unknown scope_type '{scope_type}'")
        if scope_type and not scope_id:
            raise HTTPException(400, "scope_type set but scope_id missing")

        # Dedupe on (match_type, match_value, role, scope_type, scope_id).
        existing = RoleMapping.objects(
            tenant_id=ctx.tenant_id,
            app_id=manifest.app_id,
            match_type=data.match_type,
            match_value=data.match_value,
            role=role,
            scope_type=scope_type,
            scope_id=scope_id,
        ).first()
        if existing:
            return existing.to_dict()

        mapping = RoleMapping(
            tenant_id=ctx.tenant_id,
            app_id=manifest.app_id,
            match_type=data.match_type,
            match_value=data.match_value,
            role=role,
            scope_type=scope_type,
            scope_id=scope_id,
            notes=data.notes,
            created_by=ctx.user_id,
        ).save()
        return mapping.to_dict()

    @router.delete("/mappings/{mapping_id}")
    @require_permission("roles.manage")
    async def delete_mapping(
        mapping_id: str, ctx: UserContext = Depends(get_user_context)
    ):
        row = RoleMapping.objects(
            id=mapping_id, tenant_id=ctx.tenant_id, app_id=manifest.app_id
        ).first()
        if not row:
            raise HTTPException(404, "Mapping not found")
        row.delete()
        return {"deleted": mapping_id}

    # ─── AI assistant ────────────────────────────────────────────────────
    # LLM translates plain-English admin prompts into validated action
    # proposals (create_role / assign_role / create_mapping). No auto-apply:
    # the UI makes the admin click per action, and each apply hits the
    # regular endpoints above (same validation, same authorization).

    @router.post("/assist")
    @require_permission("roles.manage")
    async def assist(
        data: AssistRequest, ctx: UserContext = Depends(get_user_context)
    ):
        from services.admin_assistant import propose_actions

        # Reuse the same manifest dict the UI gets (so catalog, scope_types,
        # and seed roles are in sync across every surface).
        manifest_dict = {
            "scope_types": [
                {"id": st.id, "label": st.label, "description": st.description}
                for st in manifest.scope_types
            ],
            "permissions": {
                perm: {"label": meta.label, "description": meta.description, "group": meta.group}
                for perm, meta in manifest.permissions.items()
            },
        }

        roles = [
            r.to_dict()
            for r in Role.objects(tenant_id=ctx.tenant_id, app_id=manifest.app_id)
        ]

        # Collect live scope resources for every declared scope type, so the
        # LLM can resolve human names ("HR library") to ids. We load these
        # dynamically so the prompt stays accurate as data changes.
        scope_options: dict[str, list[dict]] = {}
        for st in manifest.scope_types:
            items = _load_scope_items(st.id, ctx.tenant_id)
            if items:
                scope_options[st.id] = items

        # Current state — helps the LLM detect duplicates and understand
        # "what's already in place" before proposing changes.
        current_mappings = [
            m.to_dict()
            for m in RoleMapping.objects(tenant_id=ctx.tenant_id, app_id=manifest.app_id)
        ]
        current_assignment_count = RoleAssignment.objects(
            tenant_id=ctx.tenant_id, app_id=manifest.app_id
        ).count()

        result = propose_actions(
            admin_request=data.prompt,
            manifest_dict=manifest_dict,
            roles=roles,
            scope_options=scope_options,
            app_identity=manifest.app_identity,
            current_mappings=current_mappings,
            current_assignment_count=current_assignment_count,
        )
        return result

    return router


def _load_scope_items(scope_type_id: str, tenant_id: str) -> list[dict]:
    """Load {id, name} pairs for a given scope type, used by the AI
    assistant to resolve human names → ids in proposed actions.

    Known scope types are looked up directly against their models. Unknown
    types return [] (the assistant then can't resolve names for them — it
    surfaces a warning to the admin)."""
    try:
        if scope_type_id == "owner_group":
            from models.owner_group import OwnerGroup  # type: ignore

            return [
                {"id": str(g.id), "name": g.name}
                for g in OwnerGroup.objects(tenant_id=tenant_id)
            ]
        if scope_type_id == "sop":
            from models.sop import SOP  # type: ignore

            return [
                {"id": str(s.id), "name": s.title}
                for s in SOP.objects(tenant_id=tenant_id).only("id", "title").limit(100)
            ]
    except Exception:
        pass
    return []


# ── Helpers ─────────────────────────────────────────────────────────────────


def _get_role_or_404(role_id: str, ctx: UserContext, manifest: AppManifest) -> Role:
    role = Role.objects(
        id=role_id, tenant_id=ctx.tenant_id, app_id=manifest.app_id
    ).first()
    if not role:
        raise HTTPException(404, "Role not found")
    return role


def _assert_no_escalation(ctx: UserContext, requested_perms: list[str]) -> None:
    """Prevent privilege escalation: a non-SA admin can't grant permissions
    they don't themselves hold. SA bypasses."""
    if ctx.is_super_admin:
        return
    missing = [p for p in requested_perms if p not in ctx.permissions]
    if missing:
        raise HTTPException(
            403,
            f"Cannot grant permissions you do not hold: {missing}",
        )
