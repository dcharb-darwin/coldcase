"""Document text extraction — single source of truth for both the chat
context builder and the inline-viewer endpoint.

Results are memoized by `(document_id, sha256)` so PDF parsing happens once
per immutable document version. Cache is process-local, bounded; for
horizontal scaling this becomes Redis later.
"""

from __future__ import annotations

from functools import lru_cache

from models import Document
from providers.document_storage import get_document_storage_provider


_LINE_PREFIX = "[L{}] "


@lru_cache(maxsize=256)
def _read(document_id: str, sha256: str, storage_uri: str, mime_type: str, filename: str) -> str:
    """Cache key includes sha256 so a re-registration with new bytes evicts."""
    storage = get_document_storage_provider()
    path = storage.resolve_path(storage_uri)
    if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n\n".join(p.extract_text() or "" for p in reader.pages)
    with open(path, "rb") as f:
        return f.read().decode("utf-8", errors="replace")


def extract_text(doc: Document) -> str:
    """Extract text from a Document. Returns empty string on failure (caller decides what to do)."""
    try:
        return _read(str(doc.id), doc.sha256, doc.storage_uri, doc.mime_type, doc.original_filename)
    except Exception:
        return ""


def number_lines(text: str) -> str:
    """Prefix each line with `[L<n>] ` so the LLM has stable anchors to cite and
    the UI viewer can highlight the exact line on click."""
    return "\n".join(_LINE_PREFIX.format(i + 1) + line for i, line in enumerate(text.splitlines()))
