"""Cold Case provider seams.

Only the two seams this app actually uses are exported here. The starter-kit
mock-employee / mock-calendar / etc. files remain on disk as references but
are not imported (they target a different domain).
"""

from __future__ import annotations

from providers.document_storage import get_document_storage_provider
from providers.llm import get_llm_provider

__all__ = ["get_document_storage_provider", "get_llm_provider"]
