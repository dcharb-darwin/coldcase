"""Document text extraction — single source of truth for both the chat
context builder and the inline-viewer endpoint.

For PDFs we try the cheap path first (pypdf reads any embedded text layer).
If the text layer is thin — typical for scanned investigative files like
some of the Civil Rights Cold Case records — we fall back to OCR via
pymupdf (rasterize at OCR_DPI) + pytesseract (image_to_string per page).
The same pattern is used by the sibling `ada` project's WCAG remediation
pipeline (see `ada/server-py/services/wcag/ocr.py`).

Results are memoized by `(document_id, sha256)` so PDF parsing + OCR happen
once per immutable document version. Cache is process-local, bounded; for
horizontal scaling this becomes Redis later.

Env knobs (mirror `ada`):
- COLDCASE_OCR_LANG (default "eng")
- COLDCASE_OCR_DPI (default 200)
- COLDCASE_OCR_MIN_CHARS_PER_PAGE (default 40) — below this we OCR
"""

from __future__ import annotations

import logging
import os
import shutil
from functools import lru_cache

from models import Document
from providers.document_storage import get_document_storage_provider


logger = logging.getLogger(__name__)

_LINE_PREFIX = "[L{}] "
OCR_LANG = os.environ.get("COLDCASE_OCR_LANG", "eng")
OCR_DPI = int(os.environ.get("COLDCASE_OCR_DPI", "200"))
OCR_MIN_CHARS_PER_PAGE = int(os.environ.get("COLDCASE_OCR_MIN_CHARS_PER_PAGE", "40"))


def _extract_via_pypdf(path: str) -> tuple[str, int]:
    """Returns (text, page_count). Empty text doesn't mean no pages —
    a scanned PDF has pages but no embedded text layer."""
    from pypdf import PdfReader
    reader = PdfReader(path)
    pages = [(p.extract_text() or "") for p in reader.pages]
    return "\n\n".join(pages), len(pages)


def _extract_via_ocr(path: str) -> str:
    """Render each page at OCR_DPI and run tesseract image_to_string."""
    if not shutil.which("tesseract"):
        logger.warning(
            "OCR fallback requested but `tesseract` binary not on PATH; "
            "leaving document as image-only. Install with "
            "`apt-get install tesseract-ocr`."
        )
        return ""
    try:
        import pymupdf
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        logger.warning("OCR deps missing (%s); skipping OCR fallback", exc)
        return ""

    out_pages: list[str] = []
    with pymupdf.open(path) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=OCR_DPI, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            try:
                text = pytesseract.image_to_string(img, lang=OCR_LANG) or ""
            except Exception as exc:  # noqa: BLE001
                logger.warning("OCR failed on page %s: %s", page.number, exc)
                text = ""
            out_pages.append(text.strip())
    return "\n\n".join(out_pages)


@lru_cache(maxsize=256)
def _read(document_id: str, sha256: str, storage_uri: str, mime_type: str, filename: str) -> str:
    """Cache key includes sha256 so a re-registration with new bytes evicts."""
    storage = get_document_storage_provider()
    path = storage.resolve_path(storage_uri)

    is_pdf = mime_type == "application/pdf" or filename.lower().endswith(".pdf")
    if not is_pdf:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", errors="replace")

    text, page_count = _extract_via_pypdf(path)
    if page_count == 0:
        return text

    # If the embedded text layer averages fewer than OCR_MIN_CHARS_PER_PAGE
    # characters of non-whitespace per page, the PDF is effectively a scan —
    # OCR it. ada's pattern: trust the text layer when it's there.
    non_ws_chars = sum(1 for c in text if not c.isspace())
    if non_ws_chars >= OCR_MIN_CHARS_PER_PAGE * page_count:
        return text

    logger.info(
        "OCR fallback for %s (%s): pypdf got %d non-ws chars across %d pages",
        filename, document_id, non_ws_chars, page_count,
    )
    ocr_text = _extract_via_ocr(path)
    return ocr_text or text  # prefer OCR; fall back to whatever pypdf gave


def extract_text(doc: Document) -> str:
    """Extract text from a Document. Returns empty string on failure (caller decides what to do)."""
    try:
        return _read(str(doc.id), doc.sha256, doc.storage_uri, doc.mime_type, doc.original_filename)
    except Exception:
        logger.exception("extract_text failed for doc %s", doc.id)
        return ""


def number_lines(text: str) -> str:
    """Prefix each line with `[L<n>] ` so the LLM has stable anchors to cite and
    the UI viewer can highlight the exact line on click."""
    return "\n".join(_LINE_PREFIX.format(i + 1) + line for i, line in enumerate(text.splitlines()))
