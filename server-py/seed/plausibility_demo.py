"""Synthetic dataset designed to exercise every branch of the
plausibility scoring + graph layer.

Six KY cold cases 1985-2015, plus an Indiana and a South Carolina case,
populated with a person matrix that hits each code path:

  - Det. Mike Halberd — recurring KY officer across 1985, 1988, 1992,
    1994, 2003 (same role, same state, plausible career span).
    SHOULD: cluster as one person; NOT surface in conflicts (same role).

  - Marcus Webb — witness on 1988, person_of_interest on 1992 KY.
    SHOULD: surface in conflicts with high plausibility (legit Brady).

  - Diana Reeves — victim on 1985 case, witness on 2003 case (KY).
    SHOULD: surface in conflicts at moderate plausibility (one signal
    is that the person's role across decades is unusual).

  - John Williams — generic name on 1985 and 2003 (KY), different roles.
    SHOULD: surface in conflicts but with "common first+surname"
    reason flagged so detective treats with skepticism.

  - "Mike Halberd" appearance on a 2010 SC case — DIFFERENT individual.
    SHOULD: NOT cluster with the KY Mike Halberd (cross-state ORI,
    different jurisdiction → plausibility ~0.30 after multiplication).

  - "James Howell" appearance on 1955 IN case — coincidental.
    SHOULD: NOT cluster with the 1988-onward KY James Howell
    (60+ year gap → temporal score ~0.05).

Plus minimal documents on a couple of cases so the hypothesis +
inferred-mention extractors have something to read, and a sample
hypothesis with red-team data on the headline case.

All seeded cases prefix their case_number with `SYNTH-` so the
existing "show fixtures" toggle on the case list hides them by
default. The wipe endpoint deletes everything matching that prefix.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from core.dev_auth_bypass import DEV_TENANT_ID, DEV_USER_ID
from models import (
    Case, CaseClassification, CaseStatus, RetentionPolicy,
    Person, PersonRole, Provenance, ProvenanceSource,
    Tag, TagAssignment, TagSubjectKind, TagKind,
)
from models.audit_event import AuditEventType
from models.hypothesis import Hypothesis, HypothesisStatus, HypothesisOrigin
from routers._deps import CurrentUser, current_user, require_perm
from services import case_audit
from services.graph import get_graph_service


logger = logging.getLogger(__name__)


# ── Case spec ─────────────────────────────────────────────────────────────


CASE_PREFIX = "SYNTH-"


CASES: list[dict[str, Any]] = [
    # ── Kentucky (KY0240000) — the tenant's home turf, 30-year span ──
    {
        "number": f"{CASE_PREFIX}KY-1985-WALN",
        "title": "1985 — Walnut Street disappearance (Hopkinsville)",
        "description": (
            "Diana Reeves, age 19, last seen leaving the Walnut Street diner "
            "on the evening of 03/15/1985 by witness John Williams. Case "
            "remained open as missing person; reopened 2024 after new tip."
        ),
        "classification": CaseClassification.MISSING_PERSON.value,
        "date_of_incident": date(1985, 3, 15),
        "agency_ori_snapshot": "KY0240000",
    },
    {
        "number": f"{CASE_PREFIX}KY-1988-CCS",
        "title": "1988 — Christian County strangling (Cerulean)",
        "description": (
            "Female victim found 09/22/1988 at the abandoned Cerulean springs "
            "pavilion. Marcus Webb, neighbor, found the body and provided "
            "initial witness statement. No suspect charged. Detective Mike "
            "Halberd led; Det. James Howell assisted."
        ),
        "classification": CaseClassification.HOMICIDE.value,
        "date_of_incident": date(1988, 9, 22),
        "agency_ori_snapshot": "KY0240000",
    },
    {
        "number": f"{CASE_PREFIX}KY-1994-PNF",
        "title": "1994 — Pennyrile Forest unidentified remains",
        "description": (
            "Partial skeletal remains discovered 07/08/1994 by a hunter in "
            "Pennyrile State Forest. ME estimated 6-12 months post-mortem. "
            "Identity never confirmed; case remains active."
        ),
        "classification": CaseClassification.HOMICIDE.value,
        "date_of_incident": date(1994, 7, 8),
        "agency_ori_snapshot": "KY0240000",
    },
    {
        "number": f"{CASE_PREFIX}KY-2003-I24",
        "title": "2003 — I-24 corridor case (Cadiz on-ramp)",
        "description": (
            "Female victim found 11/19/2003 in a ditch off the Cadiz on-ramp "
            "to I-24. Witness Diana Reeves (age 37) reported a dark sedan "
            "leaving the area at 0210 hrs. John Williams identified later as "
            "person of interest pending lab results."
        ),
        "classification": CaseClassification.HOMICIDE.value,
        "date_of_incident": date(2003, 11, 19),
        "agency_ori_snapshot": "KY0240000",
    },
    {
        "number": f"{CASE_PREFIX}KY-2015-WBHC",
        "title": "2015 — Wendell Berry housing complex shooting",
        "description": (
            "Single GSW victim recovered 06/04/2015 at the Wendell Berry "
            "complex parking lot. Bystander interviews ongoing. Reopened "
            "2026 as cold case after lead investigator retirement."
        ),
        "classification": CaseClassification.HOMICIDE.value,
        "date_of_incident": date(2015, 6, 4),
        "agency_ori_snapshot": "KY0240000",
    },

    # ── Indiana (IN0500000) — cross-state coincidence test ──
    {
        "number": f"{CASE_PREFIX}IN-1955-EVN",
        "title": "1955 — Evansville rail yard homicide",
        "description": (
            "Adult male found in the L&N rail yard 08/20/1955 by yard worker. "
            "Officer James Howell (no relation to KY Howell — same surname, "
            "different jurisdiction, different decade) signed initial report."
        ),
        "classification": CaseClassification.HOMICIDE.value,
        "date_of_incident": date(1955, 8, 20),
        "agency_ori_snapshot": "IN0500000",
    },

    # ── South Carolina (SC0260000) — second cross-state coincidence ──
    {
        "number": f"{CASE_PREFIX}SC-2010-CHS",
        "title": "2010 — Charleston warehouse arson w/ fatality",
        "description": (
            "Industrial fire at a warehouse on 02/14/2010 with one fatality. "
            "Investigation flagged 'Mike Halberd' as a contractor of "
            "interest — separate individual from any KY namesake."
        ),
        "classification": CaseClassification.HOMICIDE.value,
        "date_of_incident": date(2010, 2, 14),
        "agency_ori_snapshot": "SC0260000",
    },
]


# Persons keyed by (case number, name). The plausibility scorer will
# (correctly) cluster the recurring KY officer and surface the legit
# Brady-risk conflicts, while dropping the cross-state coincidences.

PERSONS: list[dict[str, Any]] = [
    # ── Det. Mike Halberd — KY career, 1985 to 2003 (NO conflict — same role) ──
    {"case": "KY-1985-WALN", "name": "Det. Mike Halberd", "role": "officer",
     "descriptor": "Badge 2118, Hopkinsville PD"},
    {"case": "KY-1988-CCS",  "name": "Det. Mike Halberd", "role": "officer",
     "descriptor": "Badge 2118, Hopkinsville PD — lead detective"},
    {"case": "KY-1994-PNF",  "name": "Det. Mike Halberd", "role": "officer",
     "descriptor": "Badge 2118, Hopkinsville PD"},
    {"case": "KY-2003-I24",  "name": "Det. Mike Halberd", "role": "officer",
     "descriptor": "Badge 2118, Hopkinsville PD — retired 2010"},

    # ── Cross-state Halberd — DIFFERENT person, should NOT cluster ──
    {"case": "SC-2010-CHS",  "name": "Mike Halberd", "role": "suspect",
     "descriptor": "Charleston contractor — no known KY ties"},

    # ── Det. James Howell — KY career 1988 + 1994 (NO conflict — same role) ──
    {"case": "KY-1988-CCS",  "name": "Det. James Howell", "role": "officer",
     "descriptor": "Badge 4421, Hopkinsville PD"},
    {"case": "KY-1994-PNF",  "name": "Det. James Howell", "role": "officer",
     "descriptor": "Badge 4421, Hopkinsville PD"},

    # ── Cross-state Howell — DIFFERENT person, 33 years earlier ──
    {"case": "IN-1955-EVN",  "name": "Officer James Howell", "role": "officer",
     "descriptor": "Evansville PD, badge unknown"},

    # ── Marcus Webb — LEGIT Brady risk (witness → POI same state, short span) ──
    {"case": "KY-1988-CCS",  "name": "Marcus Webb", "role": "witness",
     "descriptor": "Neighbor at Cerulean springs scene, DOB 1955"},
    {"case": "KY-1994-PNF",  "name": "Marcus Webb", "role": "person_of_interest",
     "descriptor": "Identified from forest perimeter sighting, DOB 1955"},

    # ── Diana Reeves — moderate-confidence conflict (decades apart, KY) ──
    {"case": "KY-1985-WALN", "name": "Diana Reeves", "role": "victim",
     "descriptor": "Age 19, missing person, DOB 1966"},
    {"case": "KY-2003-I24",  "name": "Diana Reeves", "role": "witness",
     "descriptor": "Age 37, eyewitness on I-24 ramp"},

    # ── John Williams — common-name coincidence (KY both, different roles) ──
    {"case": "KY-1985-WALN", "name": "John Williams", "role": "witness",
     "descriptor": "Diner regular who saw victim leave"},
    {"case": "KY-2003-I24",  "name": "John Williams", "role": "person_of_interest",
     "descriptor": "Lab results pending"},

    # ── Some unique-to-one-case persons so the graph has texture ──
    {"case": "KY-1988-CCS",  "name": "Sgt. P. Ortiz", "role": "officer",
     "descriptor": "Badge 1772, Hopkinsville PD"},
    {"case": "KY-2015-WBHC", "name": "Sgt. P. Ortiz", "role": "officer",
     "descriptor": "Badge 1772 — same officer, end of career"},
    {"case": "KY-2015-WBHC", "name": "Janet Holloway", "role": "victim",
     "descriptor": "GSW, DOB 1981"},
    {"case": "KY-2015-WBHC", "name": "Tyrell Brooks", "role": "witness",
     "descriptor": "Resident of the complex"},
    {"case": "KY-1994-PNF",  "name": "Dr. Helen Vance", "role": "other",
     "descriptor": "County ME, forensic anthropology"},
]


# Hypotheses on the headline case to test multi-agent flow.
HYPOTHESES: list[dict[str, Any]] = [
    {
        "case": "KY-2015-WBHC",
        "title": "Janet Holloway knew her shooter",
        "body": (
            "No defensive wounds and shot was at close range; Tyrell Brooks "
            "saw the shooter approach without urgency. Suggests a known "
            "actor, not stranger violence."
        ),
        "rationale": "Brain dump from on-scene re-walk 2026-03",
        "origin": HypothesisOrigin.HUMAN_TYPED.value,
        "status": HypothesisStatus.INVESTIGATING.value,
        "bias_flags": ["anchoring"],
        "logical_gaps": [
            "Assumes Brooks's reported timeline is accurate.",
            "Doesn't account for the silenced ammunition possibility.",
        ],
        "red_team_count": 1,
    },
    {
        "case": "KY-2015-WBHC",
        "title": "Shooting was retaliatory for a prior dispute",
        "body": (
            "Two complex residents had filed harassment reports involving "
            "Holloway in the prior 90 days. Worth interviewing."
        ),
        "rationale": "AI-suggested from case docs",
        "origin": HypothesisOrigin.AI_DE_NOVO.value,
        "status": HypothesisStatus.INVESTIGATING.value,
        "bias_flags": [],
        "logical_gaps": [],
        "red_team_count": 0,
    },
]


# Tag assignments — exercise the SIMILAR_VIA_TAG edge.
TAG_ASSIGNMENTS: list[tuple[str, str]] = [
    # (case_number_suffix, tag_slug)
    ("KY-1985-WALN", "follow-up"),
    ("KY-1988-CCS", "brady-relevant"),
    ("KY-1988-CCS", "follow-up"),
    ("KY-1992-0317", "brady-relevant"),  # if existing demo case is also seeded
    ("KY-1994-PNF", "follow-up"),
    ("KY-2003-I24", "brady-relevant"),
    ("KY-2003-I24", "follow-up"),
    ("KY-2015-WBHC", "brady-relevant"),
]


# ── Seed / wipe ───────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.utcnow()


def seed_plausibility_demo(tenant_id: str, user_id: str) -> dict:
    """Idempotent. Skips cases that already exist by case_number."""
    cases_by_number: dict[str, Case] = {}

    # Cases
    created_cases = 0
    for spec in CASES:
        c = Case.objects(tenant_id=tenant_id, case_number=spec["number"]).first()
        if c is None:
            c = Case(
                tenant_id=tenant_id,
                case_number=spec["number"],
                title=spec["title"],
                classification=spec["classification"],
                retention_policy=RetentionPolicy.INDEFINITE.value,
                primary_investigator_id=user_id,
                description=spec["description"],
                date_of_incident=spec["date_of_incident"],
                agency_ori_snapshot=spec["agency_ori_snapshot"],
                created_by=user_id,
                last_activity_at=_now(),
            ).save()
            case_audit.log(
                tenant_id=tenant_id, user_id=user_id,
                event_type=AuditEventType.CASE_CREATED, case_id=str(c.id),
                summary=f"Seeded synthetic plausibility-demo case {c.case_number}",
                detail={"source": "seed.plausibility_demo"},
            )
            created_cases += 1
        cases_by_number[spec["number"].replace(CASE_PREFIX, "")] = c

    # Persons
    created_persons = 0
    for spec in PERSONS:
        case = cases_by_number.get(spec["case"])
        if case is None:
            continue
        existing = Person.objects(
            tenant_id=tenant_id, case=case, name=spec["name"], role=spec["role"],
        ).first()
        if existing:
            continue
        Person(
            tenant_id=tenant_id, case=case,
            name=spec["name"], role=spec["role"],
            descriptor=spec.get("descriptor", ""),
            created_by=user_id, created_at=_now(),
            provenance=Provenance(source=ProvenanceSource.MANUAL.value),
        ).save()
        created_persons += 1

    # Hypotheses (with bias flags + logical gaps pre-populated to test the
    # multi-agent UI without needing to actually run the red-team agent)
    created_hyps = 0
    for spec in HYPOTHESES:
        case = cases_by_number.get(spec["case"])
        if case is None:
            continue
        existing = Hypothesis.objects(
            tenant_id=tenant_id, case=case, title=spec["title"],
        ).first()
        if existing:
            continue
        Hypothesis(
            tenant_id=tenant_id, case=case,
            title=spec["title"], body=spec["body"],
            rationale=spec["rationale"],
            status=spec["status"], origin=spec["origin"],
            bias_flags=spec["bias_flags"],
            logical_gaps=spec["logical_gaps"],
            red_team_count=spec["red_team_count"],
            created_by=user_id, updated_by=user_id,
            status_changed_at=_now(),
        ).save()
        created_hyps += 1

    # Tag assignments (skip ones whose case isn't in this dataset)
    created_tags = 0
    for case_suffix, slug in TAG_ASSIGNMENTS:
        case = cases_by_number.get(case_suffix)
        if case is None:
            continue
        tag = Tag.objects(tenant_id=tenant_id, slug=slug, kind=TagKind.USER.value).first()
        if tag is None:
            continue
        existing = TagAssignment.objects(
            tenant_id=tenant_id, tag_id=str(tag.id),
            subject_kind=TagSubjectKind.CASE.value, subject_id=str(case.id),
        ).first()
        if existing:
            continue
        TagAssignment(
            tenant_id=tenant_id, tag_id=str(tag.id),
            subject_kind=TagSubjectKind.CASE.value, subject_id=str(case.id),
            case_id=str(case.id), applied_by=user_id, applied_at=_now(),
        ).save()
        created_tags += 1

    # Drop the graph cache so the next read picks up the new edges.
    try:
        get_graph_service().invalidate(tenant_id)
    except Exception:  # noqa: BLE001
        pass

    return {
        "cases_created": created_cases,
        "persons_created": created_persons,
        "hypotheses_created": created_hyps,
        "tag_assignments_created": created_tags,
        "total_cases_in_dataset": len(CASES),
        "case_numbers": [c["number"] for c in CASES],
    }


def wipe_plausibility_demo(tenant_id: str) -> dict:
    """Delete every SYNTH-prefixed case + its dependent rows for this tenant."""
    deleted_cases = 0
    deleted_persons = 0
    deleted_hyps = 0
    deleted_tag_assignments = 0
    for c in Case.objects(tenant_id=tenant_id, case_number__startswith=CASE_PREFIX):
        # Cascade by hand — these models don't define cascading deletes.
        for p in Person.objects(tenant_id=tenant_id, case=c):
            p.delete()
            deleted_persons += 1
        for h in Hypothesis.objects(tenant_id=tenant_id, case=c):
            h.delete()
            deleted_hyps += 1
        for a in TagAssignment.objects(
            tenant_id=tenant_id, subject_kind=TagSubjectKind.CASE.value,
            subject_id=str(c.id),
        ):
            a.delete()
            deleted_tag_assignments += 1
        c.delete()
        deleted_cases += 1

    try:
        get_graph_service().invalidate(tenant_id)
    except Exception:  # noqa: BLE001
        pass

    return {
        "cases_deleted": deleted_cases,
        "persons_deleted": deleted_persons,
        "hypotheses_deleted": deleted_hyps,
        "tag_assignments_deleted": deleted_tag_assignments,
    }


# ── HTTP convenience router ───────────────────────────────────────────────


router = APIRouter(prefix="/demo", tags=["Demo"])


@router.post("/seed-plausibility")
@require_perm("case.edit")
def http_seed_plausibility(user: CurrentUser = Depends(current_user)):
    """Idempotent — safe to call repeatedly. Skips anything already present."""
    return seed_plausibility_demo(user.tenant_id, user.user_id)


@router.delete("/seed-plausibility")
@require_perm("case.edit")
def http_wipe_plausibility(user: CurrentUser = Depends(current_user)):
    """Deletes every SYNTH- case + dependent rows for this tenant."""
    return wipe_plausibility_demo(user.tenant_id)


# ── CLI hook ──────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys
    from core.database import connect_db

    connect_db()
    args = sys.argv[1:]
    if "--wipe" in args:
        result = wipe_plausibility_demo(DEV_TENANT_ID)
    else:
        result = seed_plausibility_demo(DEV_TENANT_ID, DEV_USER_ID)
    import json as _json
    print(_json.dumps(result, indent=2, default=str))
