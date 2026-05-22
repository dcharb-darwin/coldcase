"""Pick the GraphService backend at runtime via env var.

Default: in-memory NetworkX. Future backends slot in here without
changing endpoint code.
"""

from __future__ import annotations

import logging
import os

from services.graph.interface import GraphService
from services.graph.networkx_backend import NetworkXGraphBackend


logger = logging.getLogger(__name__)


_singleton: GraphService | None = None


def get_graph_service() -> GraphService:
    """Process-wide singleton. The NetworkX backend keeps its own
    per-tenant cache internally so a singleton is fine."""
    global _singleton
    if _singleton is not None:
        return _singleton
    name = os.getenv("GRAPH_BACKEND", "networkx").strip().lower()
    if name in {"networkx", "memory", "default", ""}:
        _singleton = NetworkXGraphBackend()
    else:
        logger.warning(
            "graph backend %r not implemented; falling back to networkx", name,
        )
        _singleton = NetworkXGraphBackend()
    return _singleton
