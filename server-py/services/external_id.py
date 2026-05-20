"""Stable external identifiers for federated systems.

Cold Case stores per-artifact ids using its own MongoDB ObjectIds. When
an artifact is pushed to a downstream system (evidence.com, RMS, future
destinations), that system needs a stable id that:

  - is human-recognizable from the case context,
  - is unique across agencies (so federation never collides), and
  - never changes if the live agency-config env later updates.

We compose external ids hierarchically:

    case        →  {ori}:{case_number}
    document    →  {case.external_id}:doc:{doc_id}
    media       →  {case.external_id}:media:{media_id}
    report      →  {case.external_id}:report:{report_id}

The case's `external_id` is captured at create-time and stored verbatim
on the case. Child external ids are computed against the case's stored
external id (not the live env), so a later agency-ORI change does not
re-key existing artifacts.

See `docs/design/workflow-and-ux.md` §13 for the full data plan.
"""

from __future__ import annotations

import os


# Fallback when COLDCASE_AGENCY_ORI is unset (dev only). Production deploys
# fail the compliance preflight if the agency letterhead env is missing,
# so this default should never be hit in a real agency.
_FALLBACK_ORI = "UNSET"


def current_agency_ori() -> str:
    """Live ORI from env. Used only at case-creation time to snapshot."""
    return (os.getenv("COLDCASE_AGENCY_ORI") or _FALLBACK_ORI).strip()


def for_case(ori: str, case_number: str) -> str:
    """`{ori}:{case_number}` — composed once at case creation."""
    ori = (ori or _FALLBACK_ORI).strip() or _FALLBACK_ORI
    return f"{ori}:{case_number}"


def for_document(case_external_id: str, document_id: str) -> str:
    return f"{case_external_id}:doc:{document_id}"


def for_media(case_external_id: str, media_id: str) -> str:
    return f"{case_external_id}:media:{media_id}"


def for_report(case_external_id: str, report_id: str) -> str:
    return f"{case_external_id}:report:{report_id}"
