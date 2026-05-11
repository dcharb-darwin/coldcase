"""Shared FastAPI dependencies for Cold Case routers.

`CurrentUser` extends Launchpad Admin's `UserContext` so the
`require_permission` decorator's `isinstance(..., UserContext)` check
finds it — handlers can keep `user: CurrentUser = Depends(current_user)`
unchanged and gain permission enforcement just by adding the decorator.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from fastapi import Request

from launchpad_admin.context import UserContext


@dataclass
class CurrentUser(UserContext):
    """UserContext + the per-request ip_address (used in audit events)."""
    ip_address: str = ""

    @property
    def display_name(self) -> str:
        """Concatenated first+last, or the email as a fallback. Used in
        audit log summaries and on the signed-report attestation block."""
        parts = [p for p in [self.first_name, self.last_name] if p]
        return " ".join(parts) or self.email or self.user_id


def _dev_bypass_context() -> UserContext:
    return UserContext(
        user_id="dev-local-user",
        email="dev@localhost",
        first_name="Dev",
        last_name="User",
        tenant_id="dev-local-tenant",
        is_super_admin=True,  # bypasses every permission check
    )


# ── Permission decorator ────────────────────────────────────────────────────
# launchpad_admin.decorators.require_permission wraps the handler in an
# `async def` that `await`s the wrapped function — fine for async handlers,
# but our routers are mostly sync `def`. This adapter dispatches: async
# handlers go through the vendored decorator unchanged; sync handlers get
# the equivalent sync wrapper. Same permission semantics either way.

def require_perm(permission: str, *, scope_kwarg: str | None = None,
                 scope_type: str | None = None):
    import inspect
    from functools import wraps
    from fastapi import HTTPException, status
    from launchpad_admin.decorators import _find_ctx, require_permission as _orig

    def decorator(func):
        if inspect.iscoroutinefunction(func):
            return _orig(permission, scope_kwarg=scope_kwarg, scope_type=scope_type)(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
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
            return func(*args, **kwargs)

        return wrapper

    return decorator


def current_user(request: Request) -> CurrentUser:
    """Resolve the current user. Uses the Launchpad Admin middleware's
    UserContext when present; falls back to the dev bypass identity."""
    ctx: UserContext | None = getattr(request.state, "user_context", None)
    if ctx is None:
        ctx = _dev_bypass_context()
    return CurrentUser(
        **{f.name: getattr(ctx, f.name) for f in fields(UserContext)},
        ip_address=request.client.host if request.client else "",
    )
