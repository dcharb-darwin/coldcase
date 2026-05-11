"""Civil-rights-era cold case seeder.

Downloads public-domain federal investigative records from the Civil Rights
Cold Case Records Review Board (https://www.coldcaserecords.gov/) and
registers them as Cold Case `Case` + `Document` rows.

These cases were declassified by the Civil Rights Cold Case Records Collection
Act of 2018 and are in the public domain. They're historical (1940s–1950s) so
no living-victim privacy concerns, and they exercise the document chat +
citation + audit features against real investigative paperwork rather than
the synthetic Riverside Park demo.

Run via `POST /demo/seed-civil-rights` (idempotent — regenerates missing PDFs
without recreating the Case rows).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException

from lib.hash import hash_file
from models import (
    Case, CaseClassification, RetentionPolicy, Document,
)
from models.audit_event import AuditEventType
from routers._deps import CurrentUser, current_user
from services import case_audit


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceDocument:
    url: str
    filename: str  # local filename to use under uploads/civilrights/<slug>/


@dataclass(frozen=True)
class CivilRightsCase:
    case_number: str
    slug: str
    title: str
    description: str
    incident_date: str  # ISO date
    archives_catalog_id: str  # National Archives catalog id
    documents: tuple[SourceDocument, ...]


CIVIL_RIGHTS_CASES: tuple[CivilRightsCase, ...] = (
    CivilRightsCase(
        case_number="CRRA-1945-CARTER",
        slug="letha-bell-carter",
        title="1945 — Aletha (Letha) Bell Carter (Horry County, SC)",
        description=(
            "August 15, 1945, Horry County, South Carolina. Aletha Bell Carter was "
            "a 17-year-old high school student from Pine Island, Horry County. "
            "Federal investigation records declassified under the Civil Rights Cold "
            "Case Records Collection Act of 2018. Public domain (U.S. federal records, "
            "National Archives catalog 611612207)."
        ),
        incident_date="1945-08-15",
        archives_catalog_id="611612207",
        documents=(
            SourceDocument(
                url="https://www.coldcaserecords.gov/uploads/aletha-bell-carter/4-5-carter.pdf",
                filename="carter-pages-4-5.pdf",
            ),
            SourceDocument(
                url="https://www.coldcaserecords.gov/uploads/aletha-bell-carter/7-carter.pdf",
                filename="carter-page-7.pdf",
            ),
        ),
    ),
    CivilRightsCase(
        case_number="CRRA-1943-MERRITT",
        slug="alfonzo-merritt",
        title="1943 — Alfonzo Merritt (Tuscumbia, AL)",
        description=(
            "August 28, 1943, Tuscumbia, Alabama. Alfonzo Merritt was a 39-year-old "
            "coach cleaner in Tuscumbia. He was married to Annie Merritt; they had a "
            "son, Carl. Federal investigation records declassified under the Civil "
            "Rights Cold Case Records Collection Act of 2018. Public domain "
            "(National Archives catalog 611612217)."
        ),
        incident_date="1943-08-28",
        archives_catalog_id="611612217",
        documents=(
            SourceDocument(
                url="https://www.coldcaserecords.gov/uploads/alfonzo-merritt/9-10-merritt.pdf",
                filename="merritt-pages-9-10.pdf",
            ),
            SourceDocument(
                url="https://www.coldcaserecords.gov/uploads/alfonzo-merritt/13-14-merritt.pdf",
                filename="merritt-pages-13-14.pdf",
            ),
            SourceDocument(
                url="https://www.coldcaserecords.gov/uploads/alfonzo-merritt/19-merritt.pdf",
                filename="merritt-page-19.pdf",
            ),
        ),
    ),
    CivilRightsCase(
        case_number="CRRA-1954-RUSH",
        slug="eleanor-rush",
        title="1954 — Eleanor Rush (Stanly County, NC)",
        description=(
            "August 20, 1954, North Carolina. Eleanor Montgomery Rush was a "
            "17-year-old domestic worker and cleaner from Albemarle. Federal "
            "investigation records declassified under the Civil Rights Cold Case "
            "Records Collection Act of 2018. Public domain (National Archives "
            "catalog 580005196)."
        ),
        incident_date="1954-08-20",
        archives_catalog_id="580005196",
        documents=(
            SourceDocument(
                url="https://www.coldcaserecords.gov/uploads/eleanor-rush/15-17-rush.pdf",
                filename="rush-pages-15-17.pdf",
            ),
            SourceDocument(
                url="https://www.coldcaserecords.gov/uploads/eleanor-rush/44-50-rush.pdf",
                filename="rush-pages-44-50.pdf",
            ),
            SourceDocument(
                url="https://www.coldcaserecords.gov/uploads/eleanor-rush/120-rush.pdf",
                filename="rush-page-120.pdf",
            ),
            SourceDocument(
                url="https://www.coldcaserecords.gov/uploads/eleanor-rush/meltzerfinding.pdf",
                filename="rush-meltzer-finding.pdf",
            ),
        ),
    ),
)


def _download(url: str, dest: str, *, timeout: float = 60.0) -> int:
    """Download a URL to dest. Returns byte count. Raises on HTTP error."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with httpx.Client(timeout=timeout, follow_redirects=True,
                      headers={"User-Agent": "ColdCase/0.1 (research)"}) as client:
        with client.stream("GET", url) as r:
            r.raise_for_status()
            total = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(1024 * 64):
                    f.write(chunk)
                    total += len(chunk)
    return total


def _ensure_case(spec: CivilRightsCase, tenant_id: str, user_id: str, upload_dir: str) -> dict:
    """Idempotently create the Case + register its Documents.

    - If the Case doesn't exist, create it and download all PDFs.
    - If the Case exists, redownload any PDFs whose files are missing on disk.
    """
    existing = Case.objects(tenant_id=tenant_id, case_number=spec.case_number).first()
    case_dir_rel = os.path.join("civilrights", spec.slug)
    case_dir_abs = os.path.join(upload_dir, case_dir_rel)

    if existing:
        regenerated = 0
        for src in spec.documents:
            target = os.path.join(case_dir_abs, src.filename)
            if os.path.exists(target):
                continue
            logger.info("Re-downloading missing %s", src.url)
            _download(src.url, target)
            regenerated += 1
        return {
            "case_id": str(existing.id),
            "case_number": existing.case_number,
            "created": False,
            "regenerated_pdfs": regenerated,
        }

    case = Case(
        tenant_id=tenant_id,
        case_number=spec.case_number,
        title=spec.title,
        classification=CaseClassification.HOMICIDE.value,
        retention_policy=RetentionPolicy.INDEFINITE.value,
        primary_investigator_id=user_id,
        description=spec.description,
        created_by=user_id,
        last_activity_at=datetime.utcnow(),
    ).save()
    case_audit.log(
        tenant_id=tenant_id, user_id=user_id,
        event_type=AuditEventType.CASE_CREATED,
        case_id=str(case.id),
        summary=f"Seeded civil-rights cold case {spec.case_number}",
        detail={
            "source": "seed.civil_rights_cases",
            "archives_catalog_id": spec.archives_catalog_id,
            "incident_date": spec.incident_date,
        },
    )

    doc_ids: list[str] = []
    for src in spec.documents:
        target = os.path.join(case_dir_abs, src.filename)
        size = _download(src.url, target)
        sha, _ = hash_file(target)
        doc = Document(
            tenant_id=tenant_id, case=case,
            storage_uri=os.path.join(case_dir_rel, src.filename),
            sha256=sha,
            original_filename=src.filename,
            mime_type="application/pdf",
            page_count=0,  # left at 0; pypdf can compute on demand
            size_bytes=size,
            uploaded_by=user_id,
            uploaded_at=datetime.utcnow(),
        ).save()
        case_audit.log(
            tenant_id=tenant_id, user_id=user_id,
            event_type=AuditEventType.DOCUMENT_REGISTERED,
            case_id=str(case.id), document_id=str(doc.id),
            summary=f"Registered {src.filename} ({size} bytes) from {src.url}",
            detail={"source_url": src.url, "sha256": sha},
        )
        doc_ids.append(str(doc.id))

    return {
        "case_id": str(case.id),
        "case_number": case.case_number,
        "created": True,
        "documents": doc_ids,
    }


def seed_civil_rights_cases(tenant_id: str, user_id: str) -> dict:
    upload_dir = os.environ.get("UPLOAD_DIRECTORY", "./uploads")
    results = []
    errors = []
    for spec in CIVIL_RIGHTS_CASES:
        try:
            results.append(_ensure_case(spec, tenant_id, user_id, upload_dir))
        except httpx.HTTPError as exc:
            errors.append({"case_number": spec.case_number, "error": str(exc)})
            logger.exception("Failed to seed %s", spec.case_number)
    return {"cases": results, "errors": errors}


router = APIRouter(prefix="/demo", tags=["Demo"])


@router.post("/seed-civil-rights")
def http_seed_civil_rights(user: CurrentUser = Depends(current_user)):
    result = seed_civil_rights_cases(user.tenant_id, user.user_id)
    if result["errors"] and not result["cases"]:
        raise HTTPException(502, f"All case downloads failed: {result['errors']}")
    return result
