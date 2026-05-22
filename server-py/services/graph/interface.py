"""The single GraphService interface every backend implements.

Per docs/design/graph-layer.md, this is the load-bearing decision.
Today's only implementation is the in-memory NetworkX backend; future
backends (Mongo $graphLookup, Neo4j read replica) slot in behind the
same Protocol without changing a single endpoint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from services.graph.types import (
    CrossCaseWitnessHit, EdgeKind, GraphPath, Subgraph,
)


class GraphService(Protocol):
    """Tenant-scoped graph view. Every method takes `tenant_id` first.

    Mongo is the system of record; this layer is derived. Never persists;
    never replaces audit-chain operations. RBAC is honored at the endpoint
    layer above this — services may assume the caller has already passed
    `case.read` for the tenant. Cross-tenant queries are forbidden by
    convention; the type system makes it awkward by requiring `tenant_id`
    everywhere.
    """

    # ── Query 1: case neighborhood ───────────────────────────────────────

    def case_neighborhood(
        self,
        tenant_id: str,
        case_id: str,
        *,
        depth: int = 2,
        min_confidence: float = 0.4,
        include_kinds: set[str] | None = None,
    ) -> Subgraph:
        """Everything connected to this case within `depth` hops."""
        ...

    # ── Query 2: person across cases ─────────────────────────────────────

    def person_across_cases(
        self,
        tenant_id: str,
        name: str,
        *,
        exclude_case_id: str | None = None,
        min_confidence: float = 0.4,
    ) -> Subgraph:
        """All cases this person (by loose name match) appears on."""
        ...

    # ── Query 3: person network (2-hop) ──────────────────────────────────

    def person_network(
        self,
        tenant_id: str,
        name: str,
        *,
        exclude_case_id: str | None = None,
        min_confidence: float = 0.4,
    ) -> Subgraph:
        """Who else shows up with this person, across all their cases."""
        ...

    # ── Query 4: shortest path between two persons ───────────────────────

    def shortest_path_persons(
        self,
        tenant_id: str,
        source_person_id: str,
        target_person_id: str,
        *,
        max_hops: int = 5,
        min_confidence: float = 0.4,
    ) -> list[GraphPath]:
        """Find up to a few shortest paths between two persons through the
        case file. Returns multiple paths so the detective sees structural
        alternatives, not just one."""
        ...

    # ── Query 5: cross-case witness conflict ─────────────────────────────

    def cross_case_role_conflicts(
        self,
        tenant_id: str,
        *,
        min_confidence: float = 0.4,
        primary_investigator_id: str | None = None,
    ) -> list[CrossCaseWitnessHit]:
        """People who appear on multiple cases under DIFFERENT roles.
        Optionally scope to one investigator's caseload."""
        ...

    # ── Cache control (no-op for some backends) ──────────────────────────

    def invalidate(self, tenant_id: str) -> None:
        """Drop any cached representation of this tenant's graph. Called by
        write paths so the next read rebuilds from Mongo."""
        ...

    def stats(self, tenant_id: str) -> dict[str, int]:
        """Sizing diagnostics: node + edge counts by kind. Used by the
        migration-trigger heuristic (build time too high → swap backend)."""
        ...
