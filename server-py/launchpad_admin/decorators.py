"""
Permission-check decorators for FastAPI handlers.

Usage:
    from launchpad_admin.decorators import require_permission
    from launchpad_admin.middleware import get_user_context
    from launchpad_admin.context import UserContext

    @router.post("/things/")
    @require_permission("thing.create")
    async def create_thing(
        data: ThingRequest,
        ctx: UserContext = Depends(get_user_context),
    ):
        ...

The decorator finds the UserContext kwarg (added via Depends), checks the
permission, and either calls through or raises 403. SA bypass is handled
inside `ctx.can()`.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable

from fastapi import HTTPException, status

from .context import UserContext


def _find_ctx(args: tuple, kwargs: dict) -> UserContext | None:
    """Locate the UserContext argument regardless of position/name."""
    ctx = kwargs.get("ctx") or kwargs.get("user_context") or kwargs.get("user")
    if isinstance(ctx, UserContext):
        return ctx
    for a in args:
        if isinstance(a, UserContext):
            return a
    for v in kwargs.values():
        if isinstance(v, UserContext):
            return v
    return None


def require_permission(
    permission: str,
    scope_kwarg: str | None = None,
    scope_type: str | None = None,
) -> Callable:
    """Requires the caller hold `permission` — either tenant-wide or within a
    specific scope read from a request kwarg.

    Args:
        permission: Permission string to require (e.g. "sop.create").
        scope_kwarg: Handler-kwarg name whose value is the scope_id.
            When omitted, only tenant-wide grants satisfy the check.
        scope_type: Manifest ScopeType.id this scope_id belongs to
            (e.g. "owner_group", "sop"). Strongly recommended when
            scope_kwarg is set.

    Example:
        @require_permission("sop.edit_any", scope_kwarg="sop_id", scope_type="sop")
        async def edit(sop_id: str, ...): ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx = _find_ctx(args, kwargs)
            if ctx is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No authenticated user",
                )
            scope_id = kwargs.get(scope_kwarg) if scope_kwarg else None
            if not ctx.can(permission, scope_type=scope_type, scope_id=scope_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing permission: {permission}",
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_sa(func: Callable) -> Callable:
    """Shorthand — handler requires Super Admin (Govern-granted)."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        ctx = _find_ctx(args, kwargs)
        if ctx is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="No authenticated user"
            )
        if not ctx.is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Super Admin only"
            )
        return await func(*args, **kwargs)

    return wrapper


def require_role(role_name: str) -> Callable:
    """Requires the caller hold a specific role by name. Rarely the right
    check — prefer `require_permission` so custom roles work uniformly.
    Included for the narrow case of 'is this person an App Admin' UI queries."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx = _find_ctx(args, kwargs)
            if ctx is None:
                raise HTTPException(status_code=401, detail="No authenticated user")
            if not ctx.is_super_admin and not ctx.has_role(role_name):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role required: {role_name}",
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator
