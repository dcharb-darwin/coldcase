"""Shared FastAPI dependencies for Cold Case routers."""

from __future__ import annotations

from dataclasses import dataclass
from fastapi import Request


@dataclass
class CurrentUser:
    user_id: str
    tenant_id: str
    display_name: str = ""
    ip_address: str = ""


def current_user(request: Request) -> CurrentUser:
    """Resolve the current user. Uses the Launchpad Admin middleware's
    UserContext when present; falls back to the dev bypass identity."""
    # Try the launchpad_admin middleware's context first.
    ctx = getattr(request.state, "user_context", None)
    if ctx is not None:
        return CurrentUser(
            user_id=getattr(ctx, "user_id", None) or getattr(ctx, "id", "dev-local-user"),
            tenant_id=getattr(ctx, "tenant_id", "dev-local-tenant"),
            display_name=getattr(ctx, "display_name", "") or "",
            ip_address=request.client.host if request.client else "",
        )
    from core.dev_auth_bypass import DEV_USER_ID, DEV_TENANT_ID, DEV_USER_EMAIL
    return CurrentUser(
        user_id=DEV_USER_ID,
        tenant_id=DEV_TENANT_ID,
        display_name=DEV_USER_EMAIL,
        ip_address=request.client.host if request.client else "",
    )
