"""F7 — Chain-of-Custody PDF.

Renders a printable audit trail for a signed report. Auto-paired with the
signed-report PDF on every `/reports/{id}/export` call so the chain travels
with the artifact forever.

Contents (in order):
  1. Cover page with the same identifiers as the signed report + an
     audit-integrity hash that an auditor can re-derive from
     GET /audit/reports/{id}/chain.
  2. Case header.
  3. Source-document inventory (pointer-only).
  4. MediaInput inventory (§13663(c)(2)).
  5. Conversation chain — every prompt + response, discarded re-asks
     included, with refusal_detected markers.
  6. §13663(b) first AI draft (verbatim, "not an officer statement").
  7. Revision history with content hashes + signed-revision flag.
  8. AuditEvent timeline for the report.
  9. Citation-coverage stats.
  10. "How to verify" appendix.

This is a Cold Case-authored audit artifact (rule #17 carve-out), retention-
bound to the Report.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak,
)

from lib.hash import hash_text
from models.audit_event import AuditEvent
from models.case import Case
from models.conversation import Conversation
from models.message import Message
from models.media_input import MediaInput
from models import Document
from models.report import Report


_CITATION_RE = re.compile(
    r"\[src:\s*[^,\]]+?\s*,\s*(?:L\s*\d+|p\s*\d+\s*,\s*\"[^\"]+\")\s*\]",
    re.IGNORECASE,
)


def chain_audit_hash(report: Report, messages: list[Message]) -> str:
    """Audit-integrity hash an auditor can re-derive from the live
    /audit/reports/{id}/chain endpoint. Captures: the report id, the
    first-AI-draft hash, the signed-content hash, every revision hash,
    every message id+role+content hash.

    Stable: order matches the rendered chain.
    """
    parts: list[str] = [str(report.id)]
    parts.append(report.first_ai_draft_message_id or "")
    parts.append(report.signature.content_sha256 if report.signature else "")
    for r in (report.revisions or []):
        parts.append(f"r{r.seq}:{r.content_sha256}")
    for m in messages:
        parts.append(f"m{m.id}:{m.role}:{hash_text(m.content)[:16]}")
    return hash_text("|".join(parts))


def _citation_coverage(report: Report) -> dict:
    """Count citation density in the signed text.
    Paragraphs without a [src: ...] token are flagged as "unsourced".
    """
    text = report.final_text or ""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    sourced = 0
    for p in paragraphs:
        if _CITATION_RE.search(p):
            sourced += 1
    total = len(paragraphs)
    return {
        "paragraphs": total,
        "with_citations": sourced,
        "unsourced": total - sourced,
        "coverage_pct": round((sourced / total) * 100, 1) if total else 0.0,
    }


def _draw_footer(canvas, doc, *, report: Report, chain_hash: str):
    canvas.saveState()
    # Diagonal watermark
    canvas.setFont("Helvetica-Bold", 60)
    canvas.setFillColor(colors.HexColor("#fdba74"))
    canvas.setFillAlpha(0.15)
    canvas.translate(LETTER[0] / 2, LETTER[1] / 2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, "AUDIT TRAIL — NOT AN OFFICIAL REPORT")
    canvas.setFillAlpha(1.0)
    canvas.restoreState()

    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#b45309"))
    canvas.setLineWidth(0.5)
    canvas.line(0.75 * inch, 0.75 * inch, LETTER[0] - 0.75 * inch, 0.75 * inch)

    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(colors.HexColor("#b45309"))
    canvas.drawString(0.75 * inch, 0.6 * inch, "§13663(c) CHAIN OF CUSTODY — Cold Case audit artifact")

    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.black)
    case_number = report.case.case_number if report.case else "—"
    sig_prefix = (report.signature.content_sha256[:12] + "…") if report.signature else "unsigned"
    canvas.drawString(0.75 * inch, 0.48 * inch,
                      f"Cold Case Report {report.id} · Case {case_number} · signed-rev sha {sig_prefix}")

    canvas.setFont("Helvetica-Oblique", 6.5)
    canvas.drawString(0.75 * inch, 0.36 * inch,
                      f"audit-integrity sha256: {chain_hash}")
    canvas.drawString(0.75 * inch, 0.24 * inch,
                      f"Verify via: GET /launchpad/coldcase/api/audit/reports/{report.id}/chain")
    canvas.drawRightString(LETTER[0] - 0.75 * inch, 0.24 * inch, f"Page {doc.page}")
    canvas.restoreState()


def export_chain_pdf(report: Report, *, output_dir: str | None = None) -> str:
    """Render the chain-of-custody PDF. Returns the filesystem path.
    Auto-called from `POST /reports/{id}/export` so the pair is always together.
    """
    output_dir = output_dir or os.path.join(os.environ.get("UPLOAD_DIRECTORY", "./uploads"), "reports")
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{report.id}.chain.pdf")

    case: Case = report.case
    conv: Conversation = report.conversation
    messages = list(Message.objects(conversation=conv).order_by("timestamp"))
    documents = list(Document.objects(case=case).order_by("uploaded_at"))
    media_inputs = list(MediaInput.objects(case=case).order_by("registered_at"))
    audit_events = list(AuditEvent.objects(report_id=str(report.id)).order_by("timestamp"))

    chain_hash = chain_audit_hash(report, messages)
    coverage = _citation_coverage(report)

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=12.5, alignment=TA_LEFT)
    body_mono = ParagraphStyle("body_mono", parent=body, fontName="Courier", fontSize=8.5, leading=11)
    h1 = ParagraphStyle("h1", parent=styles["Title"], fontSize=15, leading=18, textColor=colors.HexColor("#92400e"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, leading=14,
                        textColor=colors.HexColor("#b45309"), spaceBefore=10, spaceAfter=4)
    note_amber = ParagraphStyle("amber", parent=body, fontSize=9, leading=12,
                                textColor=colors.HexColor("#7c2d12"),
                                backColor=colors.HexColor("#fef3c7"),
                                borderColor=colors.HexColor("#b45309"), borderWidth=0.5, borderPadding=6,
                                spaceBefore=4, spaceAfter=8)
    refusal_red = ParagraphStyle("refusal", parent=body, fontSize=9, leading=12,
                                 textColor=colors.HexColor("#7f1d1d"),
                                 backColor=colors.HexColor("#fee2e2"),
                                 borderColor=colors.HexColor("#b91c1c"), borderWidth=0.5, borderPadding=4,
                                 spaceBefore=4, spaceAfter=4)
    user_bubble = ParagraphStyle("user_bubble", parent=body, fontSize=9, leading=12,
                                 backColor=colors.HexColor("#dbeafe"), borderColor=colors.HexColor("#93c5fd"),
                                 borderWidth=0.4, borderPadding=4, spaceBefore=4, spaceAfter=2)
    assistant_bubble = ParagraphStyle("assistant_bubble", parent=body, fontSize=9, leading=12,
                                      backColor=colors.HexColor("#f1f5f9"), borderColor=colors.HexColor("#cbd5e1"),
                                      borderWidth=0.4, borderPadding=4, spaceBefore=2, spaceAfter=8)

    signer = report.signature.display_name or report.signature.user_id if report.signature else "—"

    pdf = SimpleDocTemplate(
        path, pagesize=LETTER,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=1.05 * inch,
        title=f"Chain of Custody — Cold Case Report {report.id}",
        author=signer,
        subject="Cold Case Report — chain of custody (§13663(c) audit trail)",
        keywords=", ".join([
            f"report_id={report.id}",
            f"case_number={case.case_number if case else ''}",
            f"audit_integrity_sha256={chain_hash}",
            "cold-case", "audit-trail", "penal-code-13663", "section-c",
        ]),
        creator="Cold Case (Darwin Launchpad)",
        producer="Cold Case · ReportLab",
    )

    story: list[Any] = []

    # ── 1. Cover ─────────────────────────────────────────────────────
    story.append(Paragraph("Chain of Custody", h1))
    story.append(Paragraph(f"<b>{report.title}</b>", h2))
    cover_rows = [
        ["Report ID:", str(report.id)],
        ["Case number:", case.case_number if case else "—"],
        ["First AI draft (message id):", report.first_ai_draft_message_id or "—"],
        ["Conversation id:", str(conv.id) if conv else "—"],
        ["Signed-content sha256:", report.signature.content_sha256 if report.signature else "unsigned"],
        ["Signer:", signer + (f" · badge {report.signature.badge_number}" if report.signature and report.signature.badge_number else "")],
        ["Signed at:", report.signed_at.isoformat() if report.signed_at else "—"],
        ["Audit-integrity sha256:", chain_hash],
        ["AI program(s) used:", "; ".join(f"{p.name} {p.version}".strip() for p in (report.ai_programs_used or [])) or "—"],
        ["Generated:", datetime.utcnow().isoformat() + "Z"],
    ]
    t = Table(cover_rows, colWidths=[2.0 * inch, 4.4 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#fef3c7")),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#b45309")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#fcd34d")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>This document is the §13663(c) audit trail for the Cold Case Report identified above.</b> "
        "It is <b>not</b> an official report. It exists so that defense counsel, prosecutors, and city "
        "attorneys can trace every prompt, every AI response, every officer revision, and every "
        "supporting document that produced the official report — all the way back to source. "
        "An auditor with only this PDF can re-derive the audit-integrity sha256 above by re-running "
        "the public chain endpoint named at the bottom of every page.",
        note_amber,
    ))

    # ── 2. Source documents ─────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Source documents", h2))
    if documents:
        rows = [["Filename", "Type", "Size (bytes)", "sha256 (first 16)"]]
        for d in documents:
            rows.append([d.original_filename, d.mime_type or "—", f"{d.size_bytes:,}", d.sha256[:16] + "…"])
        tt = Table(rows, colWidths=[3.0 * inch, 1.2 * inch, 1.0 * inch, 1.4 * inch])
        tt.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ]))
        story.append(tt)
    else:
        story.append(Paragraph("(no source documents registered to this case)", body))

    # ── 3. Media inputs (§13663(c)(2)) ──────────────────────────────
    story.append(Paragraph("Media inputs (§13663(c)(2))", h2))
    if media_inputs:
        rows = [["Source type", "Duration (s)", "Captured at", "sha256 (first 16)", "Description"]]
        for m in media_inputs:
            rows.append([
                m.source_type, str(m.duration_seconds),
                m.captured_at.isoformat() if m.captured_at else "—",
                m.sha256[:16] + "…",
                (m.description or "")[:80],
            ])
        tt = Table(rows, colWidths=[1.1 * inch, 0.8 * inch, 1.3 * inch, 1.3 * inch, 2.1 * inch])
        tt.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ]))
        story.append(tt)
    else:
        story.append(Paragraph(
            "(no audio/video media registered as input to this case — §13663(c)(2) trivially satisfied)",
            body,
        ))

    # ── 4. Conversation chain ───────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Conversation chain — every prompt and response", h2))
    story.append(Paragraph(
        "Discarded re-asks are included. Where the AI hedged about document access despite "
        "documents being supplied, a <b>refusal detected</b> marker appears. The §13663(b) "
        "first AI draft is the assistant message flagged below as <b>FIRST AI DRAFT</b>.",
        body,
    ))
    story.append(Spacer(1, 6))

    for m in messages:
        ts = m.timestamp.isoformat() if m.timestamp else ""
        if m.role == "user":
            story.append(Paragraph(f"<b>USER</b> · {ts} · {m.user_id}", body))
            story.append(Paragraph(_escape(m.content), user_bubble))
        else:
            flags = []
            if m.is_first_ai_draft and str(m.id) == report.first_ai_draft_message_id:
                flags.append("FIRST AI DRAFT (§13663(b))")
            extra = (m.extra or {})
            if extra.get("refusal_detected"):
                flags.append("⚠ REFUSAL DETECTED")
            flag_str = (" · " + " · ".join(flags)) if flags else ""
            model_str = f" · {m.provider}:{m.model}" if m.model else ""
            story.append(Paragraph(
                f"<b>ASSISTANT</b> · {ts}{model_str}{flag_str}",
                body,
            ))
            if extra.get("refusal_detected"):
                story.append(Paragraph(
                    "This response contained refusal phrasing despite documents being supplied. "
                    "See §13663(c) audit consequences in the appendix.",
                    refusal_red,
                ))
            story.append(Paragraph(_escape(m.content), assistant_bubble))

    # ── 5. First AI draft (§13663(b)) ───────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("§13663(b) first AI draft — not an officer statement", h2))
    story.append(Paragraph(
        "<b>The text below is the unedited first draft produced solely by artificial "
        "intelligence and is retained for as long as the official report is retained, per "
        "Penal Code §13663(b). It is NOT an officer statement.</b>",
        note_amber,
    ))
    story.append(Paragraph(_escape(report.first_ai_draft_text_snapshot or ""), body_mono))

    # ── 6. Revisions ────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Revision history", h2))
    if report.revisions:
        rows = [["seq", "editor", "timestamp", "bytes", "sha256 (first 16)", "note", "signed?"]]
        for r in report.revisions:
            rows.append([
                str(r.seq),
                (r.editor_display or r.editor_id)[:24],
                r.timestamp.isoformat() if r.timestamp else "—",
                str(r.byte_count),
                r.content_sha256[:16] + "…",
                (r.note or "")[:32],
                "✓" if (report.signature and report.signature.content_sha256 == r.content_sha256) else "",
            ])
        tt = Table(rows, colWidths=[0.4 * inch, 1.4 * inch, 1.4 * inch, 0.6 * inch, 1.2 * inch, 1.3 * inch, 0.5 * inch])
        tt.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ]))
        story.append(tt)
    else:
        story.append(Paragraph("(no revisions recorded)", body))

    # ── 7. Audit events ─────────────────────────────────────────────
    story.append(Paragraph("Audit events for this report", h2))
    if audit_events:
        rows = [["Timestamp", "Event", "User", "Summary"]]
        for e in audit_events:
            rows.append([
                e.timestamp.isoformat() if e.timestamp else "—",
                e.event_type,
                (e.user_display or e.user_id)[:24],
                (e.summary or "")[:70],
            ])
        tt = Table(rows, colWidths=[1.3 * inch, 1.4 * inch, 1.2 * inch, 2.9 * inch])
        tt.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ]))
        story.append(tt)
    else:
        story.append(Paragraph("(no audit events recorded)", body))

    # ── 8. Citation coverage ────────────────────────────────────────
    story.append(Paragraph("Citation coverage of the signed report", h2))
    story.append(Paragraph(
        f"<b>{coverage['with_citations']}</b> of <b>{coverage['paragraphs']}</b> "
        f"factual paragraphs in the signed report carry a [src: …] citation token "
        f"(<b>{coverage['coverage_pct']}%</b> coverage). "
        f"<b>{coverage['unsourced']}</b> paragraph(s) without a citation. "
        f"Anything less than 100% is a flag for the auditor to review unsourced material.",
        body,
    ))

    # ── 9. How to verify ────────────────────────────────────────────
    story.append(Paragraph("How to verify this chain", h2))
    story.append(Paragraph(
        f"1. Fetch the live audit chain: <code>GET /launchpad/coldcase/api/audit/reports/{report.id}/chain</code><br/>"
        f"2. Concatenate the same fields used to derive this PDF's audit-integrity hash: "
        f"<code>report_id | first_ai_draft_message_id | signed_content_sha256 | "
        f"each revision's sha256 in order | each message's id+role+sha256(content)[:16]</code>.<br/>"
        f"3. <code>sha256(concat)</code> should equal the value printed on every page: "
        f"<b>{chain_hash}</b>.<br/>"
        f"4. Any deviation indicates either this PDF has been tampered with or the live chain has changed "
        f"(e.g., a revision was added after export — should never happen since the Report is signed and immutable).<br/><br/>"
        f"<b>Statutory hooks:</b> §13663(a)(1) disclosure on the signed report; §13663(a)(2) officer "
        f"attestation; §13663(b) first-AI-draft retention; §13663(c)(1) audit trail identifies user; "
        f"§13663(c)(2) audit trail identifies media inputs.",
        body,
    ))

    def _on_page(canvas, doc_):
        _draw_footer(canvas, doc_, report=report, chain_hash=chain_hash)

    pdf.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return path


def _escape(text: str) -> str:
    """Make a string safe for ReportLab's mini-HTML paragraph parser."""
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
