"""Seed default domain data for local dev + first-boot.

Idempotent. Only seeds what cold case needs:
  - dev-user admin role assignment so the Admin panel is usable locally.
  - a single demo case so the UI has something to render on first boot.

Domain-specific seeders for documents / conversations / reports are deliberately
omitted — those are synthetic data that should ship in `seed/` under a separate
script, not run on every startup.
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def seed_dev_admin_assignment(tenant_id: str, user_id: str, app_id: str) -> bool:
    """Grant dev user the `admin` role in dev tenant so the Admin panel works
    locally. Safe no-op in production: the dev user id doesn't exist there."""
    from launchpad_admin.models import Role, RoleAssignment

    admin_role = Role.objects(
        tenant_id=tenant_id, app_id=app_id, name="admin"
    ).first()
    if not admin_role:
        logger.warning(
            "Cannot seed dev admin assignment: 'admin' role not found "
            "(did system role seed run?)"
        )
        return False

    existing = RoleAssignment.objects(
        user_id=user_id, tenant_id=tenant_id, app_id=app_id,
        role=admin_role, scope_id=None,
    ).first()
    if existing:
        return False

    RoleAssignment(
        user_id=user_id, tenant_id=tenant_id, app_id=app_id,
        role=admin_role, scope_id=None, granted_by="seed",
    ).save()
    logger.info("Seeded admin RoleAssignment for dev user %s", user_id)
    return True


def seed_demo_case(tenant_id: str, user_id: str) -> bool:
    """A single demo case so the frontend has something on first boot."""
    from models import Case

    if Case.objects(tenant_id=tenant_id).first():
        return False
    Case(
        tenant_id=tenant_id,
        case_number="CC-2026-0001",
        title="Demo cold case — replace with real data",
        classification="other",
        retention_policy="match_official_report",
        primary_investigator_id=user_id,
        created_by=user_id,
        description=(
            "This is a placeholder case created by `seed_defaults.seed_demo_case`. "
            "Delete it once you have real cases registered."
        ),
    ).save()
    logger.info("Seeded demo Case CC-2026-0001 for tenant %s", tenant_id)
    return True


def backfill_external_ids(tenant_id: str) -> dict:
    """Idempotent backfill of the federated-system `external_id` field added
    in docs/design/workflow-and-ux.md §13. New cases get their id at
    create-time; this catches cases (and their docs/media/reports) that
    pre-date the schema change."""
    from models import Case, Document, MediaInput
    from models.report import Report
    from services import external_id as ext_id

    cases = Case.objects(tenant_id=tenant_id, external_id__in=[None, ""])
    case_n = doc_n = media_n = report_n = 0
    ori = ext_id.current_agency_ori()
    for case in cases:
        case.external_id = ext_id.for_case(
            case.agency_ori_snapshot or ori, case.case_number
        )
        if not case.agency_ori_snapshot:
            case.agency_ori_snapshot = ori
        case.save()
        case_n += 1

    # Pass 2: any case (even those with an external_id already) may have
    # child artifacts created before the schema added external_id.
    for case in Case.objects(tenant_id=tenant_id):
        if not case.external_id:
            continue
        for d in Document.objects(case=case, external_id__in=[None, ""]):
            d.external_id = ext_id.for_document(case.external_id, str(d.id))
            d.save(); doc_n += 1
        for m in MediaInput.objects(case=case, external_id__in=[None, ""]):
            m.external_id = ext_id.for_media(case.external_id, str(m.id))
            m.save(); media_n += 1
        for r in Report.objects(case=case, external_id__in=[None, ""]):
            r.external_id = ext_id.for_report(case.external_id, str(r.id))
            r.save(); report_n += 1

    if case_n or doc_n or media_n or report_n:
        logger.info(
            "Backfilled external_id: %d cases, %d docs, %d media, %d reports",
            case_n, doc_n, media_n, report_n,
        )
    return {
        "cases_backfilled": case_n,
        "documents_backfilled": doc_n,
        "media_backfilled": media_n,
        "reports_backfilled": report_n,
    }


def seed_tag_vocabulary(tenant_id: str) -> int:
    """Closed agency vocabulary — only added on first boot or when a new
    starter entry ships. Idempotent: existing slugs are left alone."""
    from models import Tag, TagKind, TagSubjectKind

    starter = [
        # (slug, label, color, applicable_to, description)
        ("brady-relevant", "Brady-relevant", "red", ["case", "document", "message"],
         "Material that may be exculpatory under Brady v. Maryland — flag for the city attorney."),
        ("follow-up", "Follow-up", "amber", ["case", "document", "message"],
         "Needs further investigation before the case can move forward."),
        ("suspect", "Suspect", "red", ["case", "document"],
         "Document or case pertaining to an identified suspect."),
        ("witness", "Witness", "blue", ["case", "document"],
         "Witness statement or related material."),
        ("alibi", "Alibi", "indigo", ["document", "message"],
         "Material supporting or undermining an alibi."),
        ("forensics", "Forensics", "emerald", ["case", "document"],
         "Lab results, ballistics, DNA, fingerprint, or similar forensic evidence."),
        ("cleared", "Cleared", "slate", ["case"],
         "Case has been cleared — closed without further action."),
        ("cold", "Cold", "slate", ["case"],
         "No active leads — case is in cold storage but not closed."),
    ]
    created = 0
    for slug, label, color, applicable_to, description in starter:
        if Tag.objects(tenant_id=tenant_id, slug=slug).first():
            continue
        Tag(
            tenant_id=tenant_id, slug=slug, label=label,
            color=color, applicable_to=applicable_to,
            description=description,
            kind=TagKind.USER.value, created_by="seed",
        ).save()
        created += 1
    if created:
        logger.info("Seeded %d starter tags for tenant %s", created, tenant_id)
    return created


def seed_all(tenant_id: str, dev_user_id: str, app_id: str) -> dict:
    return {
        "dev_admin_assignment_created": seed_dev_admin_assignment(
            tenant_id, dev_user_id, app_id
        ),
        "demo_case_created": seed_demo_case(tenant_id, dev_user_id),
        "external_id_backfill": backfill_external_ids(tenant_id),
        "starter_tags_seeded": seed_tag_vocabulary(tenant_id),
    }
