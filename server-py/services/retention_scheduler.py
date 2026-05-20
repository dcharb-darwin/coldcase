"""Daily retention sweeper background task.

§13663(b) requires the first AI draft to persist for as long as its
official report. The sweeper service (`services/retention_sweeper.py`)
enforces that floor when it purges expired data. This module wires it
to a daily cadence so retention *actually runs* in deployment — without
this loop, the sweeper is dead code.

Started from FastAPI's `lifespan` on app startup; stopped on shutdown.
Status is queryable via `is_running()` for the compliance preflight.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from core.dev_auth_bypass import DEV_TENANT_ID
from models.audit_event import AuditEventType
from services import case_audit, retention_sweeper

logger = logging.getLogger(__name__)

# 24h cadence; small enough that an out-of-band manual sweep
# (POST /admin/retention/sweep) before the next tick is rare.
SWEEP_INTERVAL_SECONDS = 24 * 60 * 60

# Initial delay so app startup isn't blocked by a sweep + so a restart
# loop doesn't hammer Mongo. 60s gives readiness probes time to flip green.
INITIAL_DELAY_SECONDS = 60

_task: Optional[asyncio.Task] = None
_last_run_at: Optional[datetime] = None
_last_error: Optional[str] = None


def is_running() -> bool:
    """True if the scheduler loop is alive. Surfaced by the compliance preflight."""
    return _task is not None and not _task.done()


def last_run_at() -> Optional[datetime]:
    return _last_run_at


def last_error() -> Optional[str]:
    return _last_error


def _run_sweep() -> None:
    """One sweep pass. Synchronous (Mongo driver is sync) — run in a thread
    via `asyncio.to_thread` so we don't block the event loop."""
    global _last_run_at, _last_error
    try:
        report = retention_sweeper.sweep(
            tenant_id=DEV_TENANT_ID,
            apply=True,
            actor_user_id="system",
            actor_display="Retention Scheduler",
        )
        case_audit.log(
            tenant_id=DEV_TENANT_ID,
            user_id="system",
            user_display="Retention Scheduler",
            event_type=AuditEventType.RETENTION_SWEEP_COMPLETED,
            summary=(
                f"Daily retention sweep: {report.inspected} cases inspected, "
                f"{report.cases_purged} purged, "
                f"{report.first_drafts_preserved} first-drafts preserved"
            ),
            detail=report.to_dict(),
        )
        _last_run_at = datetime.utcnow()
        _last_error = None
        logger.info(
            "Retention sweep complete: inspected=%d purged=%d first_drafts_preserved=%d",
            report.inspected, report.cases_purged, report.first_drafts_preserved,
        )
    except Exception as exc:  # noqa: BLE001 — the loop must survive any single failure
        _last_error = f"{type(exc).__name__}: {exc}"
        logger.exception("Retention sweep failed: %s", exc)


async def _loop() -> None:
    await asyncio.sleep(INITIAL_DELAY_SECONDS)
    while True:
        await asyncio.to_thread(_run_sweep)
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)


def start() -> None:
    global _task
    if _task is not None and not _task.done():
        return
    loop = asyncio.get_event_loop()
    _task = loop.create_task(_loop(), name="retention-scheduler")
    logger.info("Retention scheduler started (interval=%ds)", SWEEP_INTERVAL_SECONDS)


async def stop() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except (asyncio.CancelledError, Exception):
        pass
    _task = None
    logger.info("Retention scheduler stopped")
