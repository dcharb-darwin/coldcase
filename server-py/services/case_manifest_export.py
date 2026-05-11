"""F15 — Per-Case Audit Manifest PDF.

Sibling to F7 (chain-of-custody PDF, which is per-report). F15 is the
case-level rollup an auditor wants when reviewing "everything Cold Case
knows about this case."

Sections:
  1. Case header (number, title, classification, retention, status, dates)
  2. Reports on this case (one row per report)
  3. Source-document inventory
  4. MediaInput inventory (§13663(c)(2))
  5. Distinct AI programs across the case
  6. AuditEvent counts by type
  7. How to drill down to per-report chains (F7)
"""

from __future__ import annotations

import os
from collections import Counter
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

from lib.citations import citation_coverage
from lib.reportlab_helpers import default_table_style, escape_html
from models import Document
from models.audit_event import AuditEvent
from models.case import Case
from models.media_input import MediaInput
from models.report import Report


def _draw_footer(canvas, doc, case: Case):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#475569"))
    canvas.setLineWidth(0.5)
    canvas.line(0.75 * inch, 0.75 * inch, LETTER[0] - 0.75 * inch, 0.75 * inch)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(colors.HexColor("#1e3a8a"))
    canvas.drawString(0.75 * inch, 0.6 * inch, "CASE AUDIT MANIFEST — Cold Case (Darwin Launchpad)")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.black)
    canvas.drawString(0.75 * inch, 0.48 * inch,
                      f"Case {case.case_number} · tenant {case.tenant_id} · "
                      f"generated {datetime.utcnow().isoformat()}Z")
    canvas.drawRightString(LETTER[0] - 0.75 * inch, 0.48 * inch, f"Page {doc.page}")
    canvas.restoreState()


def export_case_manifest_pdf(case: Case, *, output_dir: str | None = None) -> str:
    output_dir = output_dir or os.path.join(
        os.environ.get("UPLOAD_DIRECTORY", "./uploads"), "manifests"
    )
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{case.id}.manifest.pdf")

    reports = list(Report.objects(case=case).order_by("created_at"))
    documents = list(Document.objects(case=case).order_by("uploaded_at"))
    media_inputs = list(MediaInput.objects(case=case).order_by("registered_at"))
    audit_events = list(AuditEvent.objects(case_id=str(case.id)))

    # AI-program rollup across all reports on this case.
    program_counter: Counter = Counter()
    for r in reports:
        for p in (r.ai_programs_used or []):
            program_counter[(p.name or "", p.version or "")] += 1

    # AuditEvent counts by type.
    event_counts: Counter = Counter(e.event_type for e in audit_events)

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=12.5, alignment=TA_LEFT)
    h1 = ParagraphStyle("h1", parent=styles["Title"], fontSize=15, leading=18, textColor=colors.HexColor("#1e3a8a"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, leading=14,
                        textColor=colors.HexColor("#1e3a8a"), spaceBefore=10, spaceAfter=4)

    from lib.agency_branding import top_margin_for_branding
    pdf = SimpleDocTemplate(
        path, pagesize=LETTER,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=top_margin_for_branding(), bottomMargin=0.95 * inch,
        title=f"Case Audit Manifest — {case.case_number}",
        author="Cold Case (Darwin Launchpad)",
        subject="Cold Case — case audit manifest",
        keywords=", ".join([
            f"case_id={case.id}", f"case_number={case.case_number}",
            "cold-case", "case-manifest", "penal-code-13663",
        ]),
        creator="Cold Case (Darwin Launchpad)",
        producer="Cold Case · ReportLab",
    )
    story: list[Any] = []

    # 1. Cover
    story.append(Paragraph("Case Audit Manifest", h1))
    story.append(Paragraph(f"<b>{case.title}</b>", h2))
    header_rows = [
        ["Case number:", case.case_number],
        ["Classification:", case.classification],
        ["Status:", case.status],
        ["Retention policy:", case.retention_policy],
        ["Primary investigator id:", case.primary_investigator_id],
        ["Created:", case.created_at.isoformat() if case.created_at else "—"],
        ["Closed at:", case.closed_at.isoformat() if case.closed_at else "—"],
        ["Last activity:", case.last_activity_at.isoformat() if case.last_activity_at else "—"],
        ["Generated:", datetime.utcnow().isoformat() + "Z"],
    ]
    t = Table(header_rows, colWidths=[1.7 * inch, 4.7 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#dbeafe")),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#1e3a8a")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#93c5fd")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))
    if case.description:
        story.append(Paragraph(f"<i>{escape_html(case.description)}</i>", body))

    # 2. Reports
    story.append(Paragraph(f"Signed reports on this case ({sum(1 for r in reports if r.signature)})", h2))
    if reports:
        rows = [["Report ID", "Title", "Status", "Signer", "Signed at", "AI programs", "Citations"]]
        for r in reports:
            cov = citation_coverage(r.final_text)
            total, sourced, pct = cov["paragraphs"], cov["with_citations"], cov["coverage_pct"]
            signer = (r.signature.display_name if r.signature else "—")
            programs = "; ".join(f"{p.name} {p.version}".strip() for p in (r.ai_programs_used or [])) or "—"
            rows.append([
                str(r.id)[-8:],
                (r.title or "—")[:40],
                r.status,
                signer[:18],
                r.signed_at.isoformat()[:16] if r.signed_at else "—",
                programs[:30],
                f"{sourced}/{total} ({pct}%)" if total else "—",
            ])
        tt = Table(rows, colWidths=[0.7 * inch, 1.7 * inch, 0.7 * inch, 0.9 * inch,
                                    1.1 * inch, 1.5 * inch, 0.9 * inch])
        tt.setStyle(default_table_style())
        story.append(tt)
    else:
        story.append(Paragraph("(no signed reports yet)", body))

    # 3. Source documents
    story.append(Paragraph(f"Source documents ({len(documents)})", h2))
    if documents:
        rows = [["Filename", "Type", "Size", "sha256 (first 16)"]]
        for d in documents:
            rows.append([d.original_filename[:40], d.mime_type or "—",
                         f"{d.size_bytes:,}", d.sha256[:16] + "…"])
        tt = Table(rows, colWidths=[3.4 * inch, 1.2 * inch, 0.9 * inch, 1.7 * inch])
        tt.setStyle(default_table_style())
        story.append(tt)
    else:
        story.append(Paragraph("(no documents registered)", body))

    # 4. Media inputs
    story.append(Paragraph(f"Media inputs — §13663(c)(2) ({len(media_inputs)})", h2))
    if media_inputs:
        rows = [["Source type", "Duration (s)", "Captured at", "sha256 (first 16)"]]
        for m in media_inputs:
            rows.append([m.source_type, str(m.duration_seconds),
                         m.captured_at.isoformat() if m.captured_at else "—",
                         m.sha256[:16] + "…"])
        tt = Table(rows, colWidths=[1.5 * inch, 1.0 * inch, 2.0 * inch, 2.7 * inch])
        tt.setStyle(default_table_style())
        story.append(tt)
    else:
        story.append(Paragraph("(no media inputs registered — §13663(c)(2) trivially satisfied)", body))

    # 5. Distinct AI programs
    story.append(Paragraph("Distinct AI programs used on this case", h2))
    if program_counter:
        rows = [["Provider / model", "Version", "Used in N reports"]]
        for (name, version), count in program_counter.most_common():
            rows.append([name, version, str(count)])
        tt = Table(rows, colWidths=[2.5 * inch, 2.5 * inch, 1.4 * inch])
        tt.setStyle(default_table_style())
        story.append(tt)
    else:
        story.append(Paragraph("(no signed reports yet — no AI programs to list)", body))

    # 6. AuditEvent counts
    story.append(Paragraph(f"Audit-event counts ({len(audit_events)} total)", h2))
    if event_counts:
        rows = [["Event type", "Count"]]
        for et, c in sorted(event_counts.items(), key=lambda kv: -kv[1]):
            rows.append([et, str(c)])
        tt = Table(rows, colWidths=[4.0 * inch, 1.0 * inch])
        tt.setStyle(default_table_style())
        story.append(tt)

    # 7. Drilldown footer
    story.append(Paragraph("Drill down to per-report chains", h2))
    story.append(Paragraph(
        "For each signed report above, the full §13663(c) chain-of-custody PDF "
        "is available at <code>GET /launchpad/coldcase/api/reports/&lt;report_id&gt;/chain.pdf</code> "
        "(F7). The chain PDF includes every prompt, every response (including discarded re-asks), "
        "every revision with its content hash, the §13663(b) first AI draft, and an audit-integrity "
        "hash that an auditor can re-derive from the live audit-chain endpoint.",
        body,
    ))

    def _on_page(canvas, doc_):
        from lib.agency_branding import draw_letterhead
        draw_letterhead(canvas)
        _draw_footer(canvas, doc_, case)

    pdf.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return path


