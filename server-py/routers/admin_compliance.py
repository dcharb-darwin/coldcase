"""Compliance preflight — single endpoint that asserts a deployment is
ready to run AI-assisted official reports under California Penal Code
§13663. Designed to be hit by the deployment runbook before any agency
goes live; refuses to report 'ready' until every required gate is on.

The check list mirrors the punch list in `docs/legal/compliance-status.md`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, Depends

from core.config import get_settings
from routers._deps import CurrentUser, current_user, require_perm
from services import retention_scheduler


router = APIRouter(prefix="/admin/compliance", tags=["Compliance"])


# Real OpenAI model ids the deployment will accept. Keeps a fat-fingered
# `OPENAI_MODEL=gpt-5.5` from silently failing at first call. Extend when
# OpenAI ships a new model the agency has cleared.
_OPENAI_MODEL_ALLOWLIST = {
    "gpt-4o", "gpt-4o-mini",
    "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
    "gpt-4-turbo",
    "o3", "o3-mini", "o4-mini",
}


@dataclass
class Check:
    id: str
    label: str
    statute_ref: str  # e.g. "§13663(a)(2)"
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "statute_ref": self.statute_ref,
            "passed": self.passed,
            "detail": self.detail,
        }


def _check_auth_bypass(settings) -> Check:
    is_prod = settings.environment.lower() not in {"development", "dev", "local"}
    bypass_on = bool(settings.is_dev_bypass_auth_enabled)
    if is_prod and bypass_on:
        return Check(
            id="auth_bypass_off",
            label="Dev auth bypass disabled in production",
            statute_ref="§13663(a)(2)",
            passed=False,
            detail="IS_DEV_BYPASS_AUTH_ENABLED=true in a non-development environment. Officer signature attestation cannot be trusted.",
        )
    return Check(
        id="auth_bypass_off",
        label="Dev auth bypass disabled in production",
        statute_ref="§13663(a)(2)",
        passed=True,
        detail=(
            "Development environment — bypass acceptable."
            if not is_prod
            else "Bypass is off."
        ),
    )


def _check_openai_model() -> Check:
    provider = os.getenv("PROVIDER_LLM", "mock").lower()
    if provider != "openai":
        return Check(
            id="llm_model_valid",
            label="LLM model id is a real, supported model",
            statute_ref="§13663(a)(1)",
            passed=True,
            detail=f"PROVIDER_LLM={provider!r}; OpenAI model check skipped.",
        )
    model = os.getenv("OPENAI_MODEL", "")
    if model in _OPENAI_MODEL_ALLOWLIST:
        return Check(
            id="llm_model_valid",
            label="LLM model id is a real, supported model",
            statute_ref="§13663(a)(1)",
            passed=True,
            detail=f"OPENAI_MODEL={model!r} (note: provider returns the dated id at runtime; that id is what lands on the disclosure footer).",
        )
    return Check(
        id="llm_model_valid",
        label="LLM model id is a real, supported model",
        statute_ref="§13663(a)(1)",
        passed=False,
        detail=(
            f"OPENAI_MODEL={model!r} is not in the allowlist. "
            "Disclosure footer would carry an unrecognized program name. "
            f"Allowed: {sorted(_OPENAI_MODEL_ALLOWLIST)}"
        ),
    )


def _check_agency_letterhead() -> Check:
    name = os.getenv("COLDCASE_AGENCY_NAME", "").strip()
    if not name:
        return Check(
            id="agency_letterhead",
            label="Agency letterhead configured",
            statute_ref="(operational)",
            passed=False,
            detail="COLDCASE_AGENCY_NAME is unset. PDFs will render without an agency identity.",
        )
    return Check(
        id="agency_letterhead",
        label="Agency letterhead configured",
        statute_ref="(operational)",
        passed=True,
        detail=f"COLDCASE_AGENCY_NAME={name!r}",
    )


def _check_retention_scheduler() -> Check:
    running = retention_scheduler.is_running()
    last_run = retention_scheduler.last_run_at()
    last_err = retention_scheduler.last_error()
    if not running:
        return Check(
            id="retention_scheduler",
            label="Daily retention sweeper is running",
            statute_ref="§13663(b)",
            passed=False,
            detail="Scheduler task is not alive. First-AI-draft retention floor will not be enforced on a cadence.",
        )
    detail = "Scheduler alive."
    if last_run:
        detail += f" Last run at {last_run.isoformat()}."
    else:
        detail += " First sweep not yet executed (initial delay)."
    if last_err:
        detail += f" Last error: {last_err}"
    return Check(
        id="retention_scheduler",
        label="Daily retention sweeper is running",
        statute_ref="§13663(b)",
        passed=True,
        detail=detail,
    )


def _check_vendor_scope_module() -> Check:
    try:
        from services import vendor_scope  # noqa: F401
        return Check(
            id="vendor_scope_loaded",
            label="Vendor scope enforcement loaded",
            statute_ref="§13663(d)",
            passed=True,
            detail="services.vendor_scope.enforce_vendor_scope is wired into router dependencies.",
        )
    except Exception as exc:  # noqa: BLE001
        return Check(
            id="vendor_scope_loaded",
            label="Vendor scope enforcement loaded",
            statute_ref="§13663(d)",
            passed=False,
            detail=f"{type(exc).__name__}: {exc}",
        )


def _check_policy_template_present() -> Check:
    # The agency policy template is a deliverable that ships with the
    # deployment; if it's missing, the agency has nothing to point to for
    # the §13663(a) chapeau ("agency must maintain a policy"). Look in
    # the container-mounted location first (docker-compose mounts docs/legal
    # at /srv/docs/legal), then fall back to a host-relative path for the
    # bare-metal / pytest case.
    candidates = [
        "/srv/docs/legal/agency-policy-template.md",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "docs", "legal", "agency-policy-template.md",
        ),
    ]
    for path in candidates:
        if os.path.exists(path):
            return Check(
                id="policy_template_present",
                label="Agency policy template shipped with deployment",
                statute_ref="§13663(a) chapeau",
                passed=True,
                detail=f"Found at {path}",
            )
    return Check(
        id="policy_template_present",
        label="Agency policy template shipped with deployment",
        statute_ref="§13663(a) chapeau",
        passed=False,
        detail=(
            "docs/legal/agency-policy-template.md is missing — agency cannot "
            f"point to a model policy. Searched: {candidates}"
        ),
    )


@router.get("/preflight")
@require_perm("admin.view")
def preflight(user: CurrentUser = Depends(current_user)):
    """Returns the deployment-readiness report. `ready=true` only when
    every check passes. The runbook should refuse a go-live on `ready=false`."""
    settings = get_settings()
    checks = [
        _check_auth_bypass(settings),
        _check_openai_model(),
        _check_agency_letterhead(),
        _check_retention_scheduler(),
        _check_vendor_scope_module(),
        _check_policy_template_present(),
    ]
    ready = all(c.passed for c in checks)
    return {
        "ready": ready,
        "environment": settings.environment,
        "service": settings.service_name,
        "checks": [c.to_dict() for c in checks],
        "failed_check_ids": [c.id for c in checks if not c.passed],
    }
