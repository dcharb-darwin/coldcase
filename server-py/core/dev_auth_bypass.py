"""
Dev auth bypass for local development.
Provides a fake user context when Darwin Identity is not available.
"""

DEV_USER_ID = "dev-local-user"
DEV_USER_EMAIL = "dev@localhost"
DEV_TENANT_ID = "dev-local-tenant"
DEV_TENANT_NAME = "Local Development"
DEV_USER_ROLES = ["admin", "editor", "viewer"]
