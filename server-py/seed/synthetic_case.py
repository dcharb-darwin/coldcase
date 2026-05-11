"""Synthetic cold-case seed for demos.

Creates one fictitious homicide case with four PDF artifacts (patrol report,
detective supplemental, witness statement, ME preliminary) and two media-input
pointers (one bodycam, one interview audio). All names and details are
fictional — useful for exercising the §13663 path against real LLM responses
without exposing actual case data.

Run inline by hitting `POST /demo/seed-synthetic` (route added at the bottom
of this module) or directly via `python -m seed.synthetic_case` for CLI use.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from textwrap import dedent

from fastapi import APIRouter, Depends
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from core.dev_auth_bypass import DEV_TENANT_ID, DEV_USER_ID
from lib.hash import hash_file
from models import Case, CaseClassification, RetentionPolicy, Document, MediaInput, MediaSourceType
from routers._deps import CurrentUser, current_user
from services import case_audit
from models.audit_event import AuditEventType


# ── Fictitious narrative ────────────────────────────────────────────────────

CASE_NUMBER = "CC-1992-0317"
CASE_TITLE = "1992 Riverside Park homicide — Marlene Carrigan"
CASE_DESCRIPTION = (
    "Body of Marlene Carrigan (age 34) recovered at Riverside Park boat launch "
    "on the morning of 04/12/1992 by morning fishermen. ME ruled cause of death "
    "as blunt-force trauma to the head. No suspect charged; case reopened for "
    "cold-case review 03/2026 after DNA re-testing of preserved fingernail "
    "scrapings produced a partial profile."
)

PATROL_REPORT = dedent("""
    PATROL REPORT — INCIDENT 92-04-1107
    Reporting Officer: Ofc. James Howell, Badge 4421, B-watch
    Date / Time of Call: 04/12/1992, 06:18 hrs
    Location: Riverside Park, north boat launch, City of Westvale, CA

    Summary of Initial Observations
    At 06:18 hrs on 04/12/1992 dispatch received a 911 call from R/P David Liu
    of 412 Mulberry St. R/P reported finding what he described as "a body, a
    woman, face down" on the gravel beach north of the boat launch while
    walking his dog. I arrived on scene at 06:31 hrs. The victim, a white
    female, late 20s to mid-30s, was lying prone approximately 14 ft from the
    waterline with her head oriented east. Visible injury was a large depressed
    wound to the rear of the skull. Lividity suggested she had been deceased
    several hours. I established a perimeter using vehicle 4A-12 and the
    R/P's dog leash and called for Sgt. P. Ortiz (S-3) and detectives.

    Scene Conditions
    Overcast. Temperature ~52F. Light precipitation overnight per dispatch.
    Beach gravel was wet; partial drag-impression visible between the
    waterline and the body, approximately 9 ft long, suggesting the body
    may have been pulled from the water. No footwear impressions were
    preserved (gravel substrate).

    Items Observed (Pre-Detective Arrival, Not Collected)
    - Single brown leather sandal (right foot only) — at waterline, ~22 ft
      south of body.
    - Crumpled cocktail napkin "Boatswain's Tavern" — wedged in rocks 6 ft
      north of body.
    - Vehicle keys (Ford key + 2 unknown) on keyring, gravel beach,
      approximately 18 ft NW of body. Not associated with any vehicle in
      the parking lot at time of arrival.

    Witnesses
    R/P David Liu, dog walker, separated and re-interviewed by detectives.

    Disposition
    Scene held for detectives until arrival of Det. M. Halberd, 07:04 hrs.
""").strip()

DETECTIVE_SUPP = dedent("""
    DETECTIVE SUPPLEMENTAL — Case 92-04-1107
    Reporting Detective: Det. Mike Halberd, Badge 2118
    Date Filed: 04/14/1992

    Decedent Identification
    Decedent identified at 11:42 hrs on 04/12/1992 as Marlene M. Carrigan,
    DOB 06/03/1958, of 1217 Olive Hill Rd, Westvale. ID confirmed by next
    of kin (sister, R. Carrigan) viewing distinctive shoulder tattoo (rose
    with banner "RC", left shoulder).

    Background
    Decedent worked as a bartender at the Boatswain's Tavern, 9 Marina Way,
    confirmed by manager S. Yeoh. Decedent worked the 5pm-1am shift on
    04/11/1992. Last witnesses to see decedent alive were patrons N. Decker
    and B. Aragón at approximately 01:08 hrs at the tavern's rear parking
    lot, when she left in her vehicle (1989 Ford Tempo, plate 2RTL891).

    Vehicle Located
    Decedent's vehicle located 04/12/1992 14:11 hrs in the upper Riverside
    Park parking lot, ~340 ft from where the body was found. Driver's door
    unlocked. Driver-side window down approximately 4 inches. No visible
    blood inside the vehicle. Keys recovered from the beach (see patrol
    report) confirmed by manufacturer's code to belong to this vehicle.
    Purse with $84 cash and personal effects still inside; no apparent
    robbery.

    Persons of Interest
    - N. Decker: cooperative interview, denies seeing decedent after she
      left in vehicle. Says he walked home (lives 3 blocks from tavern).
      No vehicle of his own.
    - B. Aragón: declined a second interview after first session ended
      abruptly. Stated decedent had been "talking to a guy at the bar"
      earlier in the night but could not provide a description beyond
      "white, maybe 30s, dark jacket."
    - "Bar guy" (unknown male, dark jacket, ~30s, white): no further
      identification despite canvassing tavern regulars.

    Pending
    Forensic examination of fingernail scrapings sent to State DOJ lab,
    request 92-2210. ME final report pending toxicology. Vehicle held in
    impound; awaiting print processing.
""").strip()

WITNESS_STATEMENT = dedent("""
    WITNESS STATEMENT — Case 92-04-1107
    Witness: Brenda Aragón
    Interview: 04/13/1992, 10:22 hrs, Westvale PD, room 2
    Detective Present: Det. M. Halberd, Badge 2118
    Statement format: narrative, signed by witness

    "I went to the Boatswain's around eleven I think. Marlene was working,
    we had two or three drinks together because the place was slow. There
    was a guy at the end of the bar most of the time I was there. White guy,
    short brown hair, maybe my age or a little older. He had on a dark
    jacket, like a windbreaker or a coach's jacket. I don't know if it had
    a logo. He didn't talk to anybody but Marlene. She poured him a couple
    drinks but I don't know what they were saying. He left before we did,
    maybe 12:30 I think? I'm not totally sure on time.

    "Marlene walked me and Nick out to the parking lot around one or a
    little after. She got in her car. She had her keys out. I didn't see
    anyone else in the lot. Nick walked off toward Wilkins Street and I
    drove home. That's the last time I saw her.

    "Marlene didn't seem worried about anyone. She was in a good mood. I
    don't think she knew the guy at the bar, but I can't say for sure."

    Signed: B. Aragón
""").strip()

ME_REPORT = dedent("""
    MEDICAL EXAMINER PRELIMINARY — Case 92-04-1107
    Pathologist: Dr. R. Hsieh, M.D., County ME's Office
    Date of Autopsy: 04/13/1992

    Identification: Marlene M. Carrigan, by visual ID and dental records.

    Cause of Death: Blunt-force trauma to the posterior cranium.
    Manner of Death: Homicide (pending detective concurrence).

    Findings (selected)
    1. Single depressed skull fracture, occipital, ~7 cm wide, consistent
       with a smooth elongated implement (e.g. metal pipe, bat-end).
    2. Bilateral subdural hemorrhage. Death likely within 1-3 minutes of
       impact; no defensive evidence on hands beyond mild abrasion to
       left palm.
    3. Mild water in lungs but pulmonary edema is post-mortem in
       character; decedent did not drown.
    4. Fingernail scrapings: bilateral. Right hand yielded a small fleck
       of skin and possible blood, preserved for serology / forensic
       biology (DOJ request 92-2210).
    5. Toxicology: pending. Visible signs of recent ethanol consumption
       (~0.07-0.10 BAC range, est.) consistent with bartender duties.

    Time of Death Estimate: 02:00 - 04:30 hrs, 04/12/1992, based on
    lividity, rigor, and scene temperature. NOT consistent with body
    being in water for extended period.
""").strip()


# Canonical mapping for the synthetic Riverside Park case. Used by both
# the create path (loop) and the regenerate-missing-PDFs path (lookup).
DOCUMENT_SPECS: dict[str, tuple[str, str]] = {
    "patrol-report-92-04-1107.pdf":  ("Patrol Report — Incident 92-04-1107", PATROL_REPORT),
    "detective-supp-92-04-1107.pdf": ("Detective Supplemental — 92-04-1107", DETECTIVE_SUPP),
    "witness-statement-aragon.pdf":  ("Witness Statement — Brenda Aragón",   WITNESS_STATEMENT),
    "me-preliminary-92-04-1107.pdf": ("ME Preliminary — Carrigan, Marlene",  ME_REPORT),
}


def _make_pdf(path: str, title: str, body_text: str) -> None:
    """Render a simple PDF — enough to be parseable by Copilot/OpenAI."""
    from lib.reportlab_helpers import escape_html
    os.makedirs(os.path.dirname(path), exist_ok=True)
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=LETTER,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    story = [Paragraph(escape_html(title), styles["Title"]), Spacer(1, 12)]
    for paragraph in body_text.split("\n\n"):
        story.append(Paragraph(escape_html(paragraph), styles["BodyText"]))
        story.append(Spacer(1, 8))
    doc.build(story)


# ── Seeder ──────────────────────────────────────────────────────────────────


def seed_synthetic(tenant_id: str, user_id: str, *, upload_dir: str | None = None) -> dict:
    """Idempotent. If the Case already exists, regenerate any PDF files that
    have gone missing on disk (e.g. after a fresh container with a different
    uploads volume) so the inline viewer endpoint can still resolve them.
    """
    upload_dir = upload_dir or os.environ.get("UPLOAD_DIRECTORY", "./uploads")
    existing = Case.objects(tenant_id=tenant_id, case_number=CASE_NUMBER).first()
    if existing:
        regenerated = 0
        for d in Document.objects(case=existing):
            target = os.path.join(upload_dir, d.storage_uri)
            if os.path.exists(target):
                continue
            spec = DOCUMENT_SPECS.get(d.original_filename)
            if spec:
                title, body = spec
                _make_pdf(target, title, body)
                regenerated += 1
        return {
            "created": False,
            "case_id": str(existing.id),
            "documents": [str(d.id) for d in Document.objects(case=existing)],
            "media": [str(m.id) for m in MediaInput.objects(case=existing)],
            "regenerated_pdfs": regenerated,
        }

    case = Case(
        tenant_id=tenant_id,
        case_number=CASE_NUMBER,
        title=CASE_TITLE,
        classification=CaseClassification.HOMICIDE.value,
        retention_policy=RetentionPolicy.INDEFINITE.value,
        primary_investigator_id=user_id,
        description=CASE_DESCRIPTION,
        created_by=user_id,
        last_activity_at=datetime.utcnow(),
    ).save()

    case_audit.log(
        tenant_id=tenant_id, user_id=user_id,
        event_type=AuditEventType.CASE_CREATED,
        case_id=str(case.id),
        summary=f"Seeded synthetic demo case {CASE_NUMBER}",
        detail={"source": "seed.synthetic_case"},
    )

    doc_dir = os.path.join(upload_dir, "synthetic", "cc-1992-0317")
    doc_ids: list[str] = []
    for filename, (title, body) in DOCUMENT_SPECS.items():
        path = os.path.join(doc_dir, filename)
        _make_pdf(path, title, body)
        sha, size = hash_file(path)
        rel_uri = os.path.relpath(path, upload_dir)
        d = Document(
            tenant_id=tenant_id, case=case,
            storage_uri=rel_uri,
            sha256=sha, original_filename=filename,
            mime_type="application/pdf",
            page_count=1, size_bytes=size,
            uploaded_by=user_id,
            uploaded_at=datetime.utcnow() - timedelta(days=3),
        ).save()
        doc_ids.append(str(d.id))

    media_ids: list[str] = []
    for source_type, description, duration in [
        (MediaSourceType.BODYCAM, "Ofc. Howell — scene arrival bodycam (04/12/1992)", 1830),
        (MediaSourceType.INTERVIEW_AUDIO, "Aragón interview audio (04/13/1992)", 2200),
    ]:
        m = MediaInput(
            tenant_id=tenant_id, case=case,
            storage_uri=f"synthetic/cc-1992-0317/{source_type.value}.placeholder",
            sha256="0" * 64,  # placeholder — these media inputs are demo-only pointers
            source_type=source_type.value,
            duration_seconds=duration,
            description=description,
            registered_by=user_id,
            registered_at=datetime.utcnow() - timedelta(days=2),
        ).save()
        media_ids.append(str(m.id))

    case_audit.log(
        tenant_id=tenant_id, user_id=user_id,
        event_type=AuditEventType.DOCUMENT_REGISTERED,
        case_id=str(case.id),
        summary=f"Seeded {len(doc_ids)} synthetic documents and {len(media_ids)} media inputs",
    )

    return {
        "created": True,
        "case_id": str(case.id),
        "documents": doc_ids,
        "media": media_ids,
    }


# ── Convenience router ──────────────────────────────────────────────────────

router = APIRouter(prefix="/demo", tags=["Demo"])


@router.post("/seed-synthetic")
def http_seed_synthetic(user: CurrentUser = Depends(current_user)):
    """One-click seed for demos. Idempotent."""
    return seed_synthetic(user.tenant_id, user.user_id)


# ── CLI entry point ─────────────────────────────────────────────────────────


if __name__ == "__main__":
    from core.database import init_database
    init_database()
    result = seed_synthetic(DEV_TENANT_ID, DEV_USER_ID)
    print(result)
