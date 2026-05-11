"""
Auth router — provides /auth/me endpoint.
In dev mode, returns a fake admin user via dev_auth_bypass.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List


class TenantInfo(BaseModel):
    id: str
    name: str
    roles: List[str]


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    status: str
    current_tenant: TenantInfo


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_info():
    """Return current user info. Uses dev bypass in local mode."""
    from core.config import get_settings

    settings = get_settings()

    if settings.is_dev_bypass_auth_enabled:
        from core.dev_auth_bypass import (
            DEV_USER_ID,
            DEV_USER_EMAIL,
            DEV_TENANT_ID,
            DEV_TENANT_NAME,
            DEV_USER_ROLES,
        )

        return UserResponse(
            id=DEV_USER_ID,
            email=DEV_USER_EMAIL,
            first_name="Dev",
            last_name="User",
            status="active",
            current_tenant=TenantInfo(
                id=DEV_TENANT_ID,
                name=DEV_TENANT_NAME,
                roles=DEV_USER_ROLES,
            ),
        )

    raise HTTPException(
        status_code=501,
        detail="Darwin Identity not configured. Set IS_DEV_BYPASS_AUTH_ENABLED=true for local development.",
    )
