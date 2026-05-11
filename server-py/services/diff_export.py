"""F9 — Officer's Editorial Work (first-AI-draft vs signed-text diff).

Returns a structured diff suitable for both UI rendering and PDF export.
Computed on demand (no caching) — both ends already live on the Report row,
so there's no new persistence surface (rule #17 corollary in #20).

The diff is intentionally framed as "officer's editorial work product"
rather than "what the officer deleted from the AI" to avoid creating a
chilling effect on professional editing. Color treatment is neutral
(blue/gray) rather than green/red.
"""

from __future__ import annotations

import difflib
import os
from datetime import datetime
from typing import Literal

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from models.report import Report


DiffOp = Literal["equal", "officer_added", "ai_wrote_removed"]


def compute_diff(report: Report, *, against_seq: int | None = None) -> dict:
    """Returns a structured diff JSON. Operations are labeled in 'officer'
    terms (added / kept-from-AI / removed-from-AI-draft) rather than
    technical diff terms (+/-) to make the framing unambiguous for
    courtroom review.

    against_seq lets the caller diff against a specific revision instead of
    the signed text. Useful for during-edit self-review.
    """
    ai_first = report.first_ai_draft_text_snapshot or ""
    if against_seq is not None:
        rev = next((r for r in (report.revisions or []) if r.seq == against_seq), None)
        if rev is None:
            raise ValueError(f"no revision with seq={against_seq}")
        compare_to = rev.text
    else:
        compare_to = report.final_text or ""

    # Word-level diff over the two texts. ndiff is reasonable for
    # narrative text < 50k chars; switch to a chunked approach if needed.
    a = ai_first.split()
    b = compare_to.split()
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    segments: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            segments.append({"op": "equal", "text": " ".join(a[i1:i2])})
        elif tag == "delete":
            segments.append({"op": "ai_wrote_removed", "text": " ".join(a[i1:i2])})
        elif tag == "insert":
            segments.append({"op": "officer_added", "text": " ".join(b[j1:j2])})
        elif tag == "replace":
            segments.append({"op": "ai_wrote_removed", "text": " ".join(a[i1:i2])})
            segments.append({"op": "officer_added", "text": " ".join(b[j1:j2])})

    # Stats: percentage of AI's original draft retained verbatim.
    matcher = difflib.SequenceMatcher(a=ai_first, b=compare_to, autojunk=False)
    ratio = matcher.ratio()
    return {
        "report_id": str(report.id),
        "first_ai_draft": ai_first,
        "compared_to": compare_to,
        "compared_to_label": (
            f"signed final" if against_seq is None else f"revision seq={against_seq}"
        ),
        "segments": segments,
        "stats": {
            "ai_first_chars": len(ai_first),
            "compared_to_chars": len(compare_to),
            "similarity_ratio": round(ratio, 4),
            "no_edits": len(ai_first.strip()) > 0 and ai_first.strip() == compare_to.strip(),
        },
    }


def _draw_diff_footer(canvas, doc, *, report: Report):
    canvas.saveState()
    # Watermark
    canvas.setFont("Helvetica-Bold", 56)
    canvas.setFillColor(colors.HexColor("#1e40af"))
    canvas.setFillAlpha(0.10)
    canvas.translate(LETTER[0] / 2, LETTER[1] / 2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, "OFFICER'S EDITORIAL WORK")
    canvas.setFillAlpha(1.0)
    canvas.restoreState()

    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#1e3a8a"))
    canvas.setLineWidth(0.5)
    canvas.line(0.75 * inch, 0.75 * inch, LETTER[0] - 0.75 * inch, 0.75 * inch)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(colors.HexColor("#1e3a8a"))
    canvas.drawString(0.75 * inch, 0.6 * inch,
                      "EDITORIAL HISTORY (Penal Code §13663(b) work product) — NOT AN OFFICIAL REPORT")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.black)
    case_number = report.case.case_number if report.case else "—"
    sig_prefix = (report.signature.content_sha256[:12] + "…") if report.signature else "unsigned"
    canvas.drawString(0.75 * inch, 0.48 * inch,
                      f"Cold Case Report {report.id} · Case {case_number} · signed-rev sha {sig_prefix}")
    canvas.drawRightString(LETTER[0] - 0.75 * inch, 0.48 * inch, f"Page {doc.page}")
    canvas.restoreState()


def export_diff_pdf(report: Report, *, output_dir: str | None = None) -> str:
    """Render the editorial-work diff as a printable PDF.
    Computed on demand; file is written to disk for streaming but isn't
    persisted long-term (regenerated on each request)."""
    output_dir = output_dir or os.path.join(os.environ.get("UPLOAD_DIRECTORY", "./uploads"), "reports")
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{report.id}.diff.pdf")

    diff = compute_diff(report)
    signer = report.signature.display_name or report.signature.user_id if report.signature else "—"

    pdf = SimpleDocTemplate(
        path, pagesize=LETTER,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.95 * inch,
        title=f"Officer's editorial work — Cold Case Report {report.id}",
        author=signer,
        subject="Cold Case Report — officer's editorial work (§13663(b) audit work product)",
        keywords=", ".join([
            f"report_id={report.id}",
            f"case_number={report.case.case_number if report.case else ''}",
            "cold-case", "editorial-work", "penal-code-13663", "section-b",
        ]),
        creator="Cold Case (Darwin Launchpad)",
        producer="Cold Case · ReportLab",
    )

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=13)
    h1 = ParagraphStyle("h1", parent=styles["Title"], fontSize=15, leading=18,
                        textColor=colors.HexColor("#1e3a8a"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, leading=14,
                        textColor=colors.HexColor("#1e3a8a"), spaceBefore=10, spaceAfter=4)
    framing = ParagraphStyle("framing", parent=body, fontSize=9, leading=12,
                             textColor=colors.HexColor("#1e3a8a"),
                             backColor=colors.HexColor("#dbeafe"),
                             borderColor=colors.HexColor("#3b82f6"), borderWidth=0.5, borderPadding=8,
                             spaceBefore=4, spaceAfter=10)

    story: list = []
    story.append(Paragraph("Officer's Editorial Work", h1))
    story.append(Paragraph(f"<b>{report.title}</b>", h2))

    # Framing — explicitly avoid Brady-weaponization language.
    story.append(Paragraph(
        "<b>This document compares the AI's first draft (Penal Code §13663(b)) to the report "
        "that {signer} ultimately signed.</b><br/><br/>"
        "Removing unsupported claims, verifying facts against the source documents, and improving "
        "clarity are the officer's professional responsibilities. The AI is a tool. The officer's "
        "signature on the official report means they reviewed everything and stand behind every "
        "claim that remained.".format(signer=signer),
        framing,
    ))

    if diff["stats"]["no_edits"]:
        story.append(Paragraph(
            "<b>Officer signed the AI's first draft verbatim — no edits.</b>",
            body,
        ))
    else:
        info = [
            ["AI first draft length:", f"{diff['stats']['ai_first_chars']:,} chars"],
            ["Signed text length:", f"{diff['stats']['compared_to_chars']:,} chars"],
            ["Similarity ratio:", f"{diff['stats']['similarity_ratio']:.1%}"],
            ["Compared against:", diff["compared_to_label"]],
        ]
        t = Table(info, colWidths=[1.8 * inch, 4.4 * inch])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#dbeafe")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#1e3a8a")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#93c5fd")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

        story.append(Paragraph("Legend", h2))
        story.append(Paragraph(
            "<font color='#475569'>plain text</font> = kept from AI's first draft. "
            "<u><font color='#1e40af'>+ underlined blue</font></u> = officer added. "
            "<strike><font color='#64748b'>− strikethrough gray</font></strike> = AI wrote, officer removed.",
            body,
        ))
        story.append(Spacer(1, 8))

        story.append(Paragraph("Edits", h2))
        merged_html: list[str] = []
        for seg in diff["segments"]:
            text = _escape(seg["text"])
            if not text:
                continue
            if seg["op"] == "equal":
                merged_html.append(f"<font color='#475569'>{text}</font>")
            elif seg["op"] == "officer_added":
                merged_html.append(f"<u><font color='#1e40af'>{text}</font></u>")
            elif seg["op"] == "ai_wrote_removed":
                merged_html.append(f"<strike><font color='#64748b'>{text}</font></strike>")
        story.append(Paragraph(" ".join(merged_html), body))

    def _on_page(canvas, doc_):
        _draw_diff_footer(canvas, doc_, report=report)

    pdf.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return path


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
