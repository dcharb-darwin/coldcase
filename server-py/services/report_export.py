"""Report PDF export with the §13663 statutory disclosure.

Penal Code §13663(a)(1) requires every official report prepared with AI to
include:
  1. Identification of the AI program(s) used.
  2. The exact statement:
     "This report was written either fully or in part using artificial intelligence."
  3. The officer's signature (§13663(a)(2)) verifying review + truthfulness.

We render the disclosure as a header AND a per-page footer to remove any
ambiguity about "include". The signature block renders on the last page.

Output is a PDF written to `UPLOAD_DIRECTORY/reports/<report_id>.pdf` for MVP.
Production wires this through to evidence.com (separate export provider).
"""

from __future__ import annotations

import os
from datetime import datetime

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)
from reportlab.lib import colors

from models.report import Report


STATUTORY_DISCLOSURE = (
    "This report was written either fully or in part using artificial intelligence."
)


def _format_ai_programs(report: Report) -> str:
    parts = []
    for prog in report.ai_programs_used or []:
        bits = [prog.name]
        if prog.version:
            bits.append(f"v{prog.version}")
        if prog.provider:
            bits.append(f"({prog.provider})")
        parts.append(" ".join(bits))
    return "; ".join(parts) or "AI program identification not recorded"


def _draw_footer(canvas, doc, report: Report):
    """§13663(a)(1) compliance — the statutory disclosure renders on every page."""
    canvas.saveState()
    canvas.setStrokeColor(colors.black)
    canvas.setLineWidth(0.5)
    canvas.line(0.75 * inch, 0.75 * inch, LETTER[0] - 0.75 * inch, 0.75 * inch)

    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(0.75 * inch, 0.6 * inch, "AI DISCLOSURE (Cal. Penal Code § 13663):")
    canvas.setFont("Helvetica", 8)
    canvas.drawString(0.75 * inch, 0.48 * inch, STATUTORY_DISCLOSURE)
    canvas.drawString(
        0.75 * inch, 0.36 * inch,
        f"AI program(s) used: {_format_ai_programs(report)}",
    )
    canvas.drawRightString(
        LETTER[0] - 0.75 * inch, 0.36 * inch,
        f"Page {doc.page}",
    )
    canvas.restoreState()


def export_report_pdf(report: Report, *, output_dir: str | None = None) -> str:
    """Render the signed Report to PDF. Returns the filesystem path written.

    Raises ValueError if the report is not yet signed — §13663(a)(2) requires
    the officer's signature before this artifact has any standing.
    """
    if not report.signature:
        raise ValueError(
            "Cannot export an unsigned report — Penal Code §13663(a)(2) "
            "requires the officer's signature."
        )

    output_dir = output_dir or os.path.join(
        os.environ.get("UPLOAD_DIRECTORY", "./uploads"), "reports"
    )
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{report.id}.pdf")

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=10.5, leading=14, alignment=TA_LEFT,
    )
    title_style = ParagraphStyle(
        "title", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=16, leading=20, spaceAfter=12,
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=11, leading=14, spaceBefore=10, spaceAfter=4,
    )
    disclosure_box = ParagraphStyle(
        "disclosure", parent=body, fontName="Helvetica-Bold",
        fontSize=10, leading=13, backColor=colors.HexColor("#fef3c7"),
        borderColor=colors.HexColor("#b45309"), borderWidth=1, borderPadding=8,
        spaceBefore=4, spaceAfter=12,
    )

    doc = SimpleDocTemplate(
        path, pagesize=LETTER,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=1.0 * inch,
    )
    story = []

    # ── Cover disclosure (also on every page footer) ───────────────────────
    story.append(Paragraph(report.title or "Official Report", title_style))

    story.append(Paragraph("AI Disclosure (California Penal Code § 13663)", h2))
    story.append(Paragraph(
        f"<b>{STATUTORY_DISCLOSURE}</b><br/>"
        f"AI program(s) used: {_format_ai_programs(report)}",
        disclosure_box,
    ))

    # ── Body ───────────────────────────────────────────────────────────────
    story.append(Paragraph("Report", h2))
    for paragraph in (report.final_text or "").split("\n\n"):
        if paragraph.strip():
            story.append(Paragraph(paragraph.replace("\n", "<br/>"), body))
            story.append(Spacer(1, 6))

    # ── Officer attestation + signature ────────────────────────────────────
    story.append(Spacer(1, 18))
    story.append(Paragraph("Officer Attestation (Penal Code § 13663(a)(2))", h2))
    sig = report.signature
    story.append(Paragraph(sig.attestation_text, body))
    story.append(Spacer(1, 12))
    sig_table = Table(
        [
            ["Signed by:", sig.display_name or sig.user_id],
            ["Badge:", sig.badge_number or "—"],
            ["Date / time:", sig.signed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if sig.signed_at else "—"],
            ["Content hash (SHA-256):", sig.content_sha256],
        ],
        colWidths=[1.7 * inch, 4.5 * inch],
    )
    sig_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(sig_table)

    # ── First-AI-draft reference page (audit-friendly; §13663(b)) ──────────
    story.append(PageBreak())
    story.append(Paragraph(
        "Appendix A — First AI Draft (§ 13663(b))", h2,
    ))
    story.append(Paragraph(
        "<b>Not an officer statement.</b> The text below is the unedited "
        "first draft produced solely by artificial intelligence and is retained "
        "by the agency for as long as this official report is retained, in "
        "compliance with California Penal Code § 13663(b). This draft does not "
        "constitute the officer's statement.",
        body,
    ))
    story.append(Spacer(1, 8))
    for paragraph in (report.first_ai_draft_text_snapshot or "").split("\n\n"):
        if paragraph.strip():
            story.append(Paragraph(paragraph.replace("\n", "<br/>"), body))
            story.append(Spacer(1, 6))

    def _footer_cb(canvas, doc_):
        _draw_footer(canvas, doc_, report)

    doc.build(story, onFirstPage=_footer_cb, onLaterPages=_footer_cb)
    return path
