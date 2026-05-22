"""Multi-dimensional graph layer over the tenant's Mongo data.

Per docs/design/graph-layer.md — interface-first, swappable backends.
Default is in-memory NetworkX; future backends include Mongo
$graphLookup and Neo4j read-replica. Mongo stays the system of record;
the graph is a derived view, never persists, never touches the
§13663 audit chain.
"""

from services.graph.types import (
    EdgeKind, NodeKind, EdgeProvenanceSource, EdgeStatus,
    GraphNode, GraphEdge, Subgraph, GraphPath,
    CrossCaseWitnessHit,
)
from services.graph.interface import GraphService
from services.graph.backend_factory import get_graph_service

__all__ = [
    "EdgeKind", "NodeKind", "EdgeProvenanceSource", "EdgeStatus",
    "GraphNode", "GraphEdge", "Subgraph", "GraphPath",
    "CrossCaseWitnessHit",
    "GraphService", "get_graph_service",
]
