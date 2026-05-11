"""Shared helpers for the ReportLab-based PDF exporters
(report_export, chain_export, diff_export, case_manifest_export)."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.platypus import TableStyle


def escape_html(text: str | None) -> str:
    """Make a string safe for ReportLab's mini-HTML paragraph parser.

    Includes newline → <br/> translation so multi-line strings render as
    multi-line paragraphs (matters for chat-content rendering in chain_export).
    """
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def default_table_style(*, header_row: bool = True) -> TableStyle:
    """The repeating gray-header / thin-grid table style used by every PDF
    exporter. Pass `header_row=False` for tables without a distinct header
    (e.g., key-value rows where the first column is the labels)."""
    cmds = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header_row:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")))
        cmds.append(("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"))
    return TableStyle(cmds)
