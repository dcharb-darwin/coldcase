"""In-memory NetworkX backend for the GraphService interface.

Default implementation. Loads the tenant's full graph from Mongo on
first query, caches for 60s, runs traversals via NetworkX algorithms.

Cache invalidation is event-driven: write paths bump the tenant's
version via `invalidate(tenant_id)` and the next read rebuilds.

When a tenant outgrows in-memory (build time > 5s OR memory > 1 GB),
the same GraphService interface is implemented by `mongo_native_backend.py`
($graphLookup) or `neo4j_backend.py` (read replica) — endpoints don't
change.
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Iterable

import networkx as nx

from services.graph.loader import (
    _normalize_name, load_tenant_graph,
)
from services.graph.plausibility import same_person_plausibility
from services.graph.types import (
    CrossCaseWitnessHit,
    EdgeKind, EdgeProvenanceSource, EdgeStatus,
    GraphEdge, GraphNode, GraphPath, NodeKind,
    Subgraph, node_id, split_node_id,
)


logger = logging.getLogger(__name__)


_CACHE_TTL_SECONDS = 60.0


@dataclass
class _CacheEntry:
    graph: nx.MultiDiGraph
    nodes_by_id: dict[str, GraphNode]
    built_at: float
    node_count: int
    edge_count: int


class NetworkXGraphBackend:
    """In-memory backend. Thread-safe across requests via a coarse lock —
    rebuild contention is rare on a single tenant and the cost is paying
    a few seconds once a minute under heavy concurrent load."""

    def __init__(self) -> None:
        self._caches: dict[str, _CacheEntry] = {}
        self._lock = Lock()

    # ── Cache plumbing ───────────────────────────────────────────────────

    def _build(self, tenant_id: str) -> _CacheEntry:
        t0 = time.perf_counter()
        nodes, edges = load_tenant_graph(tenant_id)
        g = nx.MultiDiGraph()
        nodes_by_id: dict[str, GraphNode] = {}
        for n in nodes:
            nodes_by_id[n.id] = n
            g.add_node(n.id, kind=n.kind.value)
        for e in edges:
            if e.source not in nodes_by_id or e.target not in nodes_by_id:
                continue
            g.add_edge(e.source, e.target, edge=e)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "graph: built tenant=%s nodes=%d edges=%d in %.0fms",
            tenant_id, len(nodes_by_id), g.number_of_edges(), elapsed_ms,
        )
        return _CacheEntry(
            graph=g, nodes_by_id=nodes_by_id, built_at=time.time(),
            node_count=len(nodes_by_id), edge_count=g.number_of_edges(),
        )

    def _get(self, tenant_id: str) -> _CacheEntry:
        with self._lock:
            entry = self._caches.get(tenant_id)
            if entry and (time.time() - entry.built_at) < _CACHE_TTL_SECONDS:
                return entry
            entry = self._build(tenant_id)
            self._caches[tenant_id] = entry
            return entry

    def invalidate(self, tenant_id: str) -> None:
        with self._lock:
            self._caches.pop(tenant_id, None)

    def stats(self, tenant_id: str) -> dict[str, int]:
        entry = self._get(tenant_id)
        kind_counts: dict[str, int] = defaultdict(int)
        for nid in entry.nodes_by_id:
            kind, _ = split_node_id(nid)
            kind_counts[kind.value] += 1
        return {
            "node_count": entry.node_count,
            "edge_count": entry.edge_count,
            **{f"nodes_{k}": v for k, v in kind_counts.items()},
        }

    # ── Internal helpers ─────────────────────────────────────────────────

    def _edge_passes(
        self, e: GraphEdge, *,
        min_confidence: float,
        edge_kinds: set[EdgeKind] | None = None,
    ) -> bool:
        if e.status != EdgeStatus.CURRENT:
            return False
        if e.confidence < min_confidence:
            return False
        if edge_kinds and e.kind not in edge_kinds:
            return False
        return True

    def _undirected_view(self, entry: _CacheEntry) -> nx.MultiGraph:
        """An undirected view that preserves the edge payloads. We build
        on demand because most queries are directional."""
        u = nx.MultiGraph()
        for src, tgt, key, data in entry.graph.edges(keys=True, data=True):
            u.add_edge(src, tgt, key=key, **data)
        return u

    def _collect_subgraph(
        self,
        entry: _CacheEntry,
        node_ids: Iterable[str],
        *,
        min_confidence: float,
        edge_kinds: set[EdgeKind] | None = None,
        include_kinds: set[str] | None = None,
    ) -> Subgraph:
        """Materialise a Subgraph wire shape from a set of node ids."""
        node_set = set(node_ids)
        nodes: list[GraphNode] = []
        for nid in node_set:
            gn = entry.nodes_by_id.get(nid)
            if not gn:
                continue
            if include_kinds is not None and gn.kind.value not in include_kinds:
                continue
            nodes.append(gn)
        # Use `set(...)` again because include_kinds filter may have removed
        # some that other endpoints need; only emit edges whose both ends
        # are in the final node list.
        kept_ids = {n.id for n in nodes}
        edges: list[GraphEdge] = []
        for src, tgt, data in entry.graph.edges(data=True):
            if src not in kept_ids or tgt not in kept_ids:
                continue
            e: GraphEdge = data["edge"]
            if not self._edge_passes(e, min_confidence=min_confidence, edge_kinds=edge_kinds):
                continue
            edges.append(e)
        stats = self._stats_for(nodes)
        return Subgraph(nodes=nodes, edges=edges, stats=stats)

    def _stats_for(self, nodes: list[GraphNode]) -> dict[str, int]:
        d: dict[str, int] = defaultdict(int)
        for n in nodes:
            d[n.kind.value] += 1
        return dict(d)

    # ── Query 1: case neighborhood ───────────────────────────────────────

    def case_neighborhood(
        self, tenant_id: str, case_id: str, *,
        depth: int = 2,
        min_confidence: float = 0.4,
        include_kinds: set[str] | None = None,
    ) -> Subgraph:
        entry = self._get(tenant_id)
        root = node_id(NodeKind.CASE, case_id)
        if root not in entry.nodes_by_id:
            return Subgraph(nodes=[], edges=[], stats={})
        u = self._undirected_view(entry)
        # BFS up to `depth` hops over the undirected view.
        seen = {root}
        frontier = {root}
        for _ in range(max(1, min(depth, 4))):
            next_frontier: set[str] = set()
            for n in frontier:
                if n not in u:
                    continue
                for nbr in u.neighbors(n):
                    # Honor min_confidence on at least one connecting edge.
                    keep = False
                    for _key, data in u[n][nbr].items():
                        e: GraphEdge = data["edge"]
                        if self._edge_passes(e, min_confidence=min_confidence):
                            keep = True
                            break
                    if keep and nbr not in seen:
                        seen.add(nbr)
                        next_frontier.add(nbr)
            frontier = next_frontier
            if not frontier:
                break
        return self._collect_subgraph(
            entry, seen,
            min_confidence=min_confidence, include_kinds=include_kinds,
        )

    # ── Query 2: person across cases ─────────────────────────────────────

    def person_across_cases(
        self, tenant_id: str, name: str, *,
        exclude_case_id: str | None = None,
        min_confidence: float = 0.4,
    ) -> Subgraph:
        entry = self._get(tenant_id)
        target = _normalize_name(name)
        if not target:
            return Subgraph(nodes=[], edges=[], stats={})
        # Find person nodes matching the name + their case neighbors.
        person_ids: set[str] = set()
        case_ids: set[str] = set()
        for nid, gn in entry.nodes_by_id.items():
            if gn.kind != NodeKind.PERSON:
                continue
            if _normalize_name(gn.label) != target:
                continue
            case_raw = (gn.attrs or {}).get("case_id", "")
            if exclude_case_id and case_raw == exclude_case_id:
                continue
            person_ids.add(nid)
            if case_raw:
                case_ids.add(node_id(NodeKind.CASE, case_raw))
        keep = person_ids | case_ids
        return self._collect_subgraph(
            entry, keep, min_confidence=min_confidence,
            edge_kinds={EdgeKind.APPEARS_ON_CASE, EdgeKind.SAME_NAME_AS},
        )

    # ── Query 3: person network (2-hop) ──────────────────────────────────

    def person_network(
        self, tenant_id: str, name: str, *,
        exclude_case_id: str | None = None,
        min_confidence: float = 0.4,
    ) -> Subgraph:
        entry = self._get(tenant_id)
        target = _normalize_name(name)
        if not target:
            return Subgraph(nodes=[], edges=[], stats={})
        # Step 1: find person nodes matching the name.
        focal_persons: set[str] = set()
        for nid, gn in entry.nodes_by_id.items():
            if gn.kind != NodeKind.PERSON:
                continue
            if _normalize_name(gn.label) != target:
                continue
            case_raw = (gn.attrs or {}).get("case_id", "")
            if exclude_case_id and case_raw == exclude_case_id:
                continue
            focal_persons.add(nid)
        # Step 2: walk to cases and back to other persons (co-occurs).
        keep: set[str] = set(focal_persons)
        for pid in focal_persons:
            for nbr in entry.graph.successors(pid):
                kind, _ = split_node_id(nbr)
                if kind == NodeKind.CASE:
                    keep.add(nbr)
                    # All persons on that case.
                    for p2 in entry.graph.predecessors(nbr):
                        k2, _ = split_node_id(p2)
                        if k2 == NodeKind.PERSON:
                            keep.add(p2)
        return self._collect_subgraph(
            entry, keep, min_confidence=min_confidence,
            edge_kinds={EdgeKind.APPEARS_ON_CASE, EdgeKind.CO_OCCURS_WITH},
        )

    # ── Query 4: shortest path between two persons ───────────────────────

    def shortest_path_persons(
        self, tenant_id: str,
        source_person_id: str, target_person_id: str, *,
        max_hops: int = 5,
        min_confidence: float = 0.4,
    ) -> list[GraphPath]:
        entry = self._get(tenant_id)
        src = node_id(NodeKind.PERSON, source_person_id)
        tgt = node_id(NodeKind.PERSON, target_person_id)
        if src not in entry.nodes_by_id or tgt not in entry.nodes_by_id:
            return []
        # shortest_simple_paths doesn't work on MultiGraph — fold parallel
        # edges into one undirected Graph, keeping the highest-confidence
        # edge per (s,t) pair. The folded edge keeps a reference back to
        # the original GraphEdge so we can reconstruct the answer.
        u = nx.Graph()
        for s, t, data in entry.graph.edges(data=True):
            e: GraphEdge = data["edge"]
            if not self._edge_passes(e, min_confidence=min_confidence):
                continue
            if u.has_edge(s, t):
                existing: GraphEdge = u[s][t]["edge"]
                if e.confidence > existing.confidence:
                    u[s][t]["edge"] = e
            else:
                u.add_edge(s, t, edge=e)
        try:
            paths_iter = nx.shortest_simple_paths(u, source=src, target=tgt)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
        out: list[GraphPath] = []
        for path_nodes in paths_iter:
            if len(path_nodes) - 1 > max_hops:
                break
            edge_seq: list[GraphEdge] = []
            for a, b in zip(path_nodes, path_nodes[1:]):
                if not u.has_edge(a, b):
                    break
                edge_seq.append(u[a][b]["edge"])
            if len(edge_seq) != len(path_nodes) - 1:
                continue
            nodes = [entry.nodes_by_id[nid] for nid in path_nodes if nid in entry.nodes_by_id]
            total = 1.0
            for e in edge_seq:
                total *= max(e.confidence, 0.01)
            out.append(GraphPath(
                nodes=nodes, edges=edge_seq, total_confidence=round(total, 4),
            ))
            if len(out) >= 5:
                break
        return out

    # ── Query 5: cross-case role conflicts ───────────────────────────────

    def cross_case_role_conflicts(
        self, tenant_id: str, *,
        min_confidence: float = 0.4,
        primary_investigator_id: str | None = None,
        min_plausibility: float = 0.25,
    ) -> list[CrossCaseWitnessHit]:
        entry = self._get(tenant_id)
        # Bucket persons by normalized name → list of (case_id, role, ...).
        by_norm: dict[str, list[dict]] = defaultdict(list)
        for nid, gn in entry.nodes_by_id.items():
            if gn.kind != NodeKind.PERSON:
                continue
            norm = _normalize_name(gn.label)
            if not norm:
                continue
            case_raw = (gn.attrs or {}).get("case_id", "")
            role = (gn.attrs or {}).get("role", "")
            if not case_raw or not role:
                continue
            # Filter by investigator if requested.
            if primary_investigator_id:
                case_node = entry.nodes_by_id.get(node_id(NodeKind.CASE, case_raw))
                if not case_node or (case_node.attrs or {}).get("primary_investigator_id") != primary_investigator_id:
                    continue
            by_norm[norm].append({
                "person_node_id": nid,
                "case_id": case_raw,
                "role": role,
                "name": gn.label,
                "confidence": _person_appears_confidence(entry, nid, case_raw),
            })

        hits: list[CrossCaseWitnessHit] = []
        for norm, appearances in by_norm.items():
            # Need ≥ 2 distinct cases AND ≥ 2 distinct roles.
            case_ids = {a["case_id"] for a in appearances}
            roles = {a["role"] for a in appearances}
            if len(case_ids) < 2 or len(roles) < 2:
                continue
            # Filter low-confidence appearances (APPEARS_ON_CASE).
            kept = [a for a in appearances if a["confidence"] >= min_confidence]
            if len({a["case_id"] for a in kept}) < 2:
                continue
            if len({a["role"] for a in kept}) < 2:
                continue

            # Cluster appearances by pairwise plausibility so coincidental
            # name matches (e.g. 1945 case vs 1992 case, different state)
            # don't poison the hit. Same name spanning decades in one
            # state is one cluster; the unrelated 1945 case forms its
            # own cluster and only surfaces if IT alone has ≥2 cases +
            # roles (it won't with just one appearance).
            canonical_name = max(kept, key=lambda a: len(a.get("name", "")))["name"]
            distinct_cases = list({a["case_id"]: a for a in kept}.values())
            # Build pair → plausibility map.
            pair_score: dict[tuple[int, int], float] = {}
            pair_reasons: dict[tuple[int, int], list[str]] = {}
            for i, ap_a in enumerate(distinct_cases):
                a_attrs = (
                    (entry.nodes_by_id.get(node_id(NodeKind.CASE, ap_a["case_id"]))
                     or _empty_node()).attrs or {}
                )
                for j in range(i + 1, len(distinct_cases)):
                    ap_b = distinct_cases[j]
                    b_attrs = (
                        (entry.nodes_by_id.get(node_id(NodeKind.CASE, ap_b["case_id"]))
                         or _empty_node()).attrs or {}
                    )
                    pr = same_person_plausibility(
                        name=canonical_name,
                        case_a_date=_parse_date(a_attrs.get("date_of_incident")),
                        case_b_date=_parse_date(b_attrs.get("date_of_incident")),
                        case_a_ori=a_attrs.get("agency_ori_snapshot", ""),
                        case_b_ori=b_attrs.get("agency_ori_snapshot", ""),
                    )
                    pair_score[(i, j)] = pr.score
                    pair_reasons[(i, j)] = pr.reasons

            # Pull officer verdicts (CONFIRMED_SAME / CONFIRMED_DIFFERENT)
            # so we can override the heuristic for any pair the detective
            # already adjudicated.
            confirmed_same: set[frozenset[str]] = set()
            confirmed_different: set[frozenset[str]] = set()
            person_ids = [a["person_node_id"] for a in distinct_cases]
            person_id_set = set(person_ids)
            for s_, t_, data in entry.graph.edges(data=True):
                e: GraphEdge = data["edge"]
                if e.source not in person_id_set or e.target not in person_id_set:
                    continue
                pair = frozenset({e.source, e.target})
                if e.kind == EdgeKind.CONFIRMED_SAME_PERSON_AS:
                    confirmed_same.add(pair)
                elif e.kind == EdgeKind.CONFIRMED_DIFFERENT_PERSON_AS:
                    confirmed_different.add(pair)

            # Union-find over appearance indices: connect any pair whose
            # plausibility passes the threshold, force-connect officer-
            # confirmed-same pairs, and refuse to connect officer-confirmed-
            # different pairs (even if heuristic says they're the same).
            n = len(distinct_cases)
            parent = list(range(n))

            def _find(x: int) -> int:
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for (i, j), score in pair_score.items():
                pair = frozenset({distinct_cases[i]["person_node_id"],
                                  distinct_cases[j]["person_node_id"]})
                if pair in confirmed_different:
                    continue  # explicit "not the same person" — never connect
                connect = (pair in confirmed_same) or (score >= min_plausibility)
                if connect:
                    ri, rj = _find(i), _find(j)
                    if ri != rj:
                        parent[ri] = rj

            comps: dict[int, list[int]] = defaultdict(list)
            for idx in range(n):
                comps[_find(idx)].append(idx)

            for comp_indices in comps.values():
                comp_apps = [distinct_cases[idx] for idx in comp_indices]
                comp_case_ids = {a["case_id"] for a in comp_apps}
                comp_roles = {a["role"] for a in comp_apps}
                if len(comp_case_ids) < 2 or len(comp_roles) < 2:
                    continue
                # Min plausibility + union of reasons WITHIN this component.
                min_score = 1.0
                seen_reasons: set[str] = set()
                reason_set: list[str] = []
                for i_a in range(len(comp_indices)):
                    for j_a in range(i_a + 1, len(comp_indices)):
                        key = (
                            min(comp_indices[i_a], comp_indices[j_a]),
                            max(comp_indices[i_a], comp_indices[j_a]),
                        )
                        s = pair_score.get(key, 1.0)
                        if s < min_score:
                            min_score = s
                        for r in pair_reasons.get(key, []):
                            if r not in seen_reasons:
                                seen_reasons.add(r)
                                reason_set.append(r)

                full_apps: list[dict] = []
                for a in comp_apps:
                    case_node = entry.nodes_by_id.get(node_id(NodeKind.CASE, a["case_id"]))
                    attrs = (case_node.attrs or {}) if case_node else {}
                    full_apps.append({
                        **a,
                        "case_number": attrs.get("case_number", ""),
                        "case_title": attrs.get("title", ""),
                        "case_classification": attrs.get("classification", ""),
                    })
                canonical = max(comp_apps, key=lambda a: len(a.get("name", "")))
                # Does any pair in this component carry an officer
                # CONFIRMED_SAME assertion? If so the UI shows it as
                # officer-validated rather than heuristic.
                contains_confirmed = False
                comp_pids = {a["person_node_id"] for a in comp_apps}
                for i_a in range(len(comp_apps)):
                    for j_a in range(i_a + 1, len(comp_apps)):
                        pair = frozenset({comp_apps[i_a]["person_node_id"],
                                          comp_apps[j_a]["person_node_id"]})
                        if pair in confirmed_same:
                            contains_confirmed = True
                            break
                    if contains_confirmed:
                        break
                _ = comp_pids  # unused locally but documents intent
                hits.append(CrossCaseWitnessHit(
                    person_id=canonical["person_node_id"],
                    person_name=canonical["name"],
                    appearances=full_apps,
                    plausibility_score=round(min_score, 3),
                    implausibility_reasons=reason_set,
                    contains_confirmed_same=contains_confirmed,
                ))
        # Sort by plausibility DESC first (most-likely-real-conflicts up
        # top), then by # of distinct roles, then by case count.
        hits.sort(key=lambda h: (
            -h.plausibility_score,
            -len({a["role"] for a in h.appearances}),
            -len({a["case_id"] for a in h.appearances}),
        ))
        return hits


def _empty_node() -> GraphNode:
    """Sentinel for missing case nodes — keeps the inner loop tidy."""
    return GraphNode(id="", kind=NodeKind.CASE, label="", attrs={})


def _parse_date(s: str | None):
    """Round-trip ISO date strings back to datetime.date for the scorer.
    The graph nodes store ISO strings (JSON-friendly); the scorer takes
    date objects."""
    if not s:
        return None
    from datetime import date as _date
    try:
        # Handles both 'YYYY-MM-DD' and full ISO datetime.
        if "T" in s:
            return _date.fromisoformat(s.split("T", 1)[0])
        return _date.fromisoformat(s)
    except ValueError:
        return None


def _person_appears_confidence(
    entry: _CacheEntry, person_nid: str, case_raw: str,
) -> float:
    """Look up the confidence on the APPEARS_ON_CASE edge between a
    person node and a case. Default to 1.0 if not found (shouldn't
    happen — the loader emits these structurally)."""
    case_nid = node_id(NodeKind.CASE, case_raw)
    if person_nid not in entry.graph:
        return 1.0
    if not entry.graph.has_edge(person_nid, case_nid):
        return 1.0
    for _key, data in entry.graph[person_nid][case_nid].items():
        e: GraphEdge = data["edge"]
        if e.kind == EdgeKind.APPEARS_ON_CASE:
            return e.confidence
    return 1.0
