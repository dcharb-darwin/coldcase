"""
Cold Case — FastAPI application factory.

Standalone FastAPI server following Darwin Launchpad patterns
(no darwin-resty / darwin-common required for POC).
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.database import init_database, close_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    init_database()
    # Launchpad Admin — seed system roles + dev-user admin assignment (idempotent).
    try:
        from launchpad_admin.seed import seed_system_roles
        from auth.app_manifest import APP_MANIFEST
        from core.dev_auth_bypass import DEV_TENANT_ID, DEV_USER_ID
        from services.seed_defaults import seed_all

        seed_system_roles(APP_MANIFEST, tenant_id=DEV_TENANT_ID)
        seed_all(DEV_TENANT_ID, DEV_USER_ID, APP_MANIFEST.app_id)
    except Exception as exc:  # noqa: BLE001 — never block startup
        logger.warning("Launchpad Admin seeding failed: %s", exc)

    # Daily retention sweeper — §13663(b) floor enforcement. Without this
    # the sweeper service is dead code; preflight asserts it's running.
    try:
        from services import retention_scheduler
        retention_scheduler.start()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Retention scheduler failed to start: %s", exc)

    yield

    try:
        from services import retention_scheduler
        await retention_scheduler.stop()
    except Exception:  # noqa: BLE001
        pass
    close_database()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title="Cold Case",
        description="Cold case investigation, lead management, and evidence tracking for law enforcement",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Launchpad Admin middleware — attaches UserContext to every request.
    # Must be registered BEFORE routers so permission decorators can read it.
    from launchpad_admin.middleware import user_context_middleware
    application.middleware("http")(user_context_middleware)

    # Health checks (outside API prefix)
    @application.get("/live", tags=["Health"])
    async def liveness():
        return {"status": "ok"}

    @application.get("/ready", tags=["Health"])
    async def readiness():
        """Process is up; MongoDB must answer ping for 200."""
        try:
            from mongoengine.connection import get_db
            get_db().client.admin.command("ping")
        except Exception as exc:  # pragma: no cover
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "service": settings.service_name,
                    "mongodb": f"{type(exc).__name__}: {exc}",
                },
            )
        return {"status": "ok", "service": settings.service_name, "mongodb": "ok"}

    # Mount routers under API prefix
    api_prefix = f"/launchpad/{settings.service_name}/api"

    from routers.auth import router as auth_router
    application.include_router(auth_router, prefix=api_prefix)

    # Cold Case domain routers (F1, F2, F3, F4 — see docs/comprehensive-prd.md §5).
    from routers.cases import router as cases_router
    from routers.conversations import router as conversations_router
    from routers.reports import router as reports_router
    from routers.audit import router as audit_router
    from routers.prompts import router as prompts_router
    from routers.vendor_access import router as vendor_access_router
    from routers.admin_retention import router as admin_retention_router
    from routers.admin_compliance import router as admin_compliance_router
    from routers.tags import router as tags_router
    from routers.persons import router as persons_router
    from routers.timeline_entries import router as timeline_entries_router
    from routers.notes import router as notes_router
    from routers.next_steps import router as next_steps_router
    from routers.dashboard import router as dashboard_router
    from routers.hypotheses import router as hypotheses_router
    from routers.graph import router as graph_router
    from routers.person_identity import router as person_identity_router
    from seed.synthetic_case import router as demo_router
    from seed.civil_rights_cases import router as civil_rights_router
    from seed.plausibility_demo import router as plausibility_demo_router
    application.include_router(cases_router, prefix=api_prefix)
    application.include_router(conversations_router, prefix=api_prefix)
    application.include_router(reports_router, prefix=api_prefix)
    application.include_router(audit_router, prefix=api_prefix)
    application.include_router(prompts_router, prefix=api_prefix)
    application.include_router(vendor_access_router, prefix=api_prefix)
    application.include_router(admin_retention_router, prefix=api_prefix)
    application.include_router(admin_compliance_router, prefix=api_prefix)
    application.include_router(tags_router, prefix=api_prefix)
    application.include_router(persons_router, prefix=api_prefix)
    application.include_router(timeline_entries_router, prefix=api_prefix)
    application.include_router(notes_router, prefix=api_prefix)
    application.include_router(next_steps_router, prefix=api_prefix)
    application.include_router(dashboard_router, prefix=api_prefix)
    application.include_router(hypotheses_router, prefix=api_prefix)
    application.include_router(graph_router, prefix=api_prefix)
    application.include_router(person_identity_router, prefix=api_prefix)
    application.include_router(demo_router, prefix=api_prefix)
    application.include_router(civil_rights_router, prefix=api_prefix)
    application.include_router(plausibility_demo_router, prefix=api_prefix)

    # Launchpad Admin router — /admin/{manifest,me,roles,assignments,mappings,assistant}
    # Mounted LAST so its routes don't get shadowed by domain routers.
    from launchpad_admin.router import build_admin_router
    from auth.app_manifest import APP_MANIFEST

    application.include_router(
        build_admin_router(APP_MANIFEST),
        prefix=f"{api_prefix}/admin",
        tags=["admin"],
    )

    return application


app = create_app()
