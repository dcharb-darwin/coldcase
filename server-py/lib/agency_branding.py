"""Agency letterhead / branding for every Cold Case PDF artifact.

Detective Gotti's transcript called this out (line 185 of the discovery
recording): the official report PDF must look like *the agency's*
document, not a generic Cold Case page. The investigator uploads the
final PDF to evidence.com as the case-of-record; an evidence.com viewer
or defense attorney scanning it needs to see "Hopkinsville Police
Department" at the top of every page, not a Darwin demo header.

Source of truth: environment variables (one set per deployment).
Defaults are deliberately blank — if you forget to configure the env,
you get a clean unbranded page rather than the wrong agency's name.

To add a real logo: drop the file at the path in `COLDCASE_AGENCY_LOGO_PATH`
inside the backend container; ReportLab handles PNG, JPEG, and GIF.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader


@dataclass(frozen=True)
class AgencyBranding:
    name: str
    jurisdiction: str
    ori: str        # Originating Agency Identifier (FBI NCIC ID)
    address: str
    phone: str
    logo_path: str  # absolute filesystem path or empty string

    @property
    def configured(self) -> bool:
        """True if the deployment has at least an agency name. Used to
        decide whether to draw the header at all — a missing name means
        the artifact stays unbranded rather than getting a confusing
        blank-but-styled letterhead."""
        return bool(self.name.strip())

    @property
    def has_logo(self) -> bool:
        return bool(self.logo_path) and os.path.exists(self.logo_path)

    @property
    def header_height(self) -> float:
        """How much vertical space the letterhead consumes. Used by the
        exporters to reserve a topMargin large enough that body content
        doesn't overlap with the letterhead drawn in page hooks."""
        if not self.configured:
            return 0
        return 0.85 * inch


def get_agency_branding() -> AgencyBranding:
    return AgencyBranding(
        name=os.environ.get("COLDCASE_AGENCY_NAME", "").strip(),
        jurisdiction=os.environ.get("COLDCASE_AGENCY_JURISDICTION", "").strip(),
        ori=os.environ.get("COLDCASE_AGENCY_ORI", "").strip(),
        address=os.environ.get("COLDCASE_AGENCY_ADDRESS", "").strip(),
        phone=os.environ.get("COLDCASE_AGENCY_PHONE", "").strip(),
        logo_path=os.environ.get("COLDCASE_AGENCY_LOGO_PATH", "").strip(),
    )


def draw_letterhead(canvas, branding: AgencyBranding | None = None) -> None:
    """Render the agency letterhead at the top of the current canvas page.
    Called from the exporters' `onFirstPage` / `onLaterPages` callbacks.
    No-op if the deployment hasn't configured an agency name."""
    if branding is None:
        branding = get_agency_branding()
    if not branding.configured:
        return

    canvas.saveState()
    page_w = LETTER[0]
    top_y = LETTER[1] - 0.4 * inch  # baseline for the agency name

    # Logo (left) — only if file exists and is openable. Logo silently
    # vanishes on failure rather than 500-ing on the export call.
    text_x = 0.75 * inch
    if branding.has_logo:
        try:
            img = ImageReader(branding.logo_path)
            iw, ih = img.getSize()
            target_h = 0.55 * inch
            target_w = target_h * (iw / ih) if ih else target_h
            canvas.drawImage(
                img, 0.75 * inch, top_y - target_h + 0.1 * inch,
                width=target_w, height=target_h,
                preserveAspectRatio=True, mask="auto",
            )
            text_x = 0.75 * inch + target_w + 0.18 * inch
        except Exception:  # noqa: BLE001 — bad logo file must not block export
            pass

    canvas.setFillColor(colors.black)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(text_x, top_y, branding.name.upper())

    sub_y = top_y - 12
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(colors.HexColor("#374151"))
    subtitle_parts = []
    if branding.jurisdiction:
        subtitle_parts.append(branding.jurisdiction)
    if branding.ori:
        subtitle_parts.append(f"ORI: {branding.ori}")
    if subtitle_parts:
        canvas.drawString(text_x, sub_y, " · ".join(subtitle_parts))
        sub_y -= 10
    contact_parts = [p for p in [branding.address, branding.phone] if p]
    if contact_parts:
        canvas.drawString(text_x, sub_y, " · ".join(contact_parts))

    # Divider line under the letterhead — visually separates branding
    # from the report body.
    rule_y = top_y - branding.header_height + 0.15 * inch
    canvas.setStrokeColor(colors.HexColor("#9ca3af"))
    canvas.setLineWidth(0.5)
    canvas.line(0.75 * inch, rule_y, page_w - 0.75 * inch, rule_y)

    canvas.restoreState()


def top_margin_for_branding(default: float = 0.75 * inch) -> float:
    """Top margin a SimpleDocTemplate should use to leave room for the
    letterhead. Exporters call this when constructing the doc so the
    first paragraph never overlaps the agency header."""
    branding = get_agency_branding()
    if not branding.configured:
        return default
    return default + branding.header_height


# Silence unused-import warning while still exposing the module for
# pdfmetrics consumers that may want it later.
_ = pdfmetrics
