"""Shared types for the graph layer — node + edge models with the four
dimensions every edge carries (confidence, provenance, temporal, trust)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ── Node kinds ────────────────────────────────────────────────────────────


class NodeKind(str, Enum):
    PERSON = "person"
    CASE = "case"
    DOCUMENT = "document"
    HYPOTHESIS = "hypothesis"
    TAG = "tag"
    TIMELINE = "timeline_event"
    # Passage chunking deferred to a follow-up; the enum value is reserved.
    PASSAGE = "passage"


class EdgeKind(str, Enum):
    # Person edges
    APPEARS_ON_CASE = "appears_on_case"     # Person → Case
    MERGED_INTO = "merged_into"             # Person → Person (duplicate merge target)
    SAME_NAME_AS = "same_name_as"           # Person ↔ Person (loose name match)
    CO_OCCURS_WITH = "co_occurs_with"       # Person ↔ Person (share a case)

    # Document edges
    BELONGS_TO_CASE = "belongs_to_case"     # Document → Case

    # Hypothesis edges
    ABOUT_CASE = "about_case"               # Hypothesis → Case
    ALTERNATIVE_TO = "alternative_to"       # Hypothesis → Hypothesis (red-team child)
    FROM_BRAIN_DUMP = "from_brain_dump"     # Hypothesis → Case (carries braindump_id metadata)

    # Tag + similarity
    TAGGED_WITH = "tagged_with"             # any-subject → Tag
    SIMILAR_VIA_TAG = "similar_via_tag"     # Case ↔ Case (Jaccard)

    # Timeline
    EVENT_ON_CASE = "event_on_case"         # TimelineEntry → Case


# ── Edge dimensions ───────────────────────────────────────────────────────


class EdgeProvenanceSource(str, Enum):
    """Who/what asserted this edge. Closed list so backends can rely on it."""
    HUMAN_OFFICER = "human_officer"
    AI_GENERATOR = "ai_generator"             # the brain-dump → hypothesis agent
    AI_DE_NOVO = "ai_de_novo"
    AI_RED_TEAM = "ai_red_team"
    AI_INFERRED_MENTION = "ai_inferred_mention"
    DERIVED_JACCARD = "derived_jaccard"        # tag-overlap similarity
    DERIVED_SUBSTRING = "derived_substring"    # name loose-match
    DERIVED_STRUCTURAL = "derived_structural"  # belongs_to_case etc — comes from the schema


class EdgeStatus(str, Enum):
    CURRENT = "current"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"


# ── Confidence buckets (closed vocab from the design doc) ─────────────────
#
# Not enforced at the type level — confidence is a float — but every edge
# emitter should pick from these bucket midpoints to avoid drift.


CONFIDENCE_OFFICER_CONFIRMED = 0.97   # signed report / sworn statement / exact match
CONFIDENCE_OFFICER_ACCEPTED = 0.87    # detective accepted AI suggestion explicitly
CONFIDENCE_HIGH_INFERENCE = 0.70      # AI with multiple anchors
CONFIDENCE_SINGLE_SOURCE = 0.50       # AI inferred from one passage
CONFIDENCE_WEAK = 0.30                # loose match without descriptor


# ── Node + edge dataclasses ───────────────────────────────────────────────


@dataclass(frozen=True)
class GraphNode:
    """A node in the graph. `id` is namespace-prefixed to avoid collisions
    across kinds (e.g. `person:abc123`). `label` is a short human-readable
    string for UI rendering. `attrs` carries kind-specific data."""
    id: str
    kind: NodeKind
    label: str
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "label": self.label, "attrs": self.attrs}


@dataclass(frozen=True)
class GraphEdge:
    """An edge carries the four dimensions discussed in the design doc.
    Backends MUST populate all four; downstream queries filter on them."""
    kind: EdgeKind
    source: str  # GraphNode.id
    target: str  # GraphNode.id

    # 1. Confidence — how strong is the assertion?
    confidence: float = 1.0

    # 2. Provenance — who/what asserted it?
    provenance: EdgeProvenanceSource = EdgeProvenanceSource.DERIVED_STRUCTURAL
    asserted_by: str = ""            # user_id or model name
    asserted_at: datetime | None = None

    # 3. Temporal validity
    valid_from: datetime | None = None
    valid_to: datetime | None = None   # None = still current

    # 4. Trust
    status: EdgeStatus = EdgeStatus.CURRENT
    disputed_by: str = ""

    # Free-form payload (e.g. role on a case, shared tag slugs on similar_via_tag).
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "source": self.source,
            "target": self.target,
            "confidence": self.confidence,
            "provenance": self.provenance.value,
            "asserted_by": self.asserted_by,
            "asserted_at": self.asserted_at.isoformat() if self.asserted_at else None,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "status": self.status.value,
            "disputed_by": self.disputed_by,
            "attrs": self.attrs,
        }


@dataclass
class Subgraph:
    """Wire shape for any query returning multiple nodes + edges."""
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    # Counts that surface in the UI (n people, n cases, n hypotheses…).
    stats: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "stats": self.stats,
        }


@dataclass
class GraphPath:
    """A single shortest-path result. Edges are in source→target order."""
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_confidence: float          # multiplicative across edge confidences

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "total_confidence": self.total_confidence,
        }


@dataclass
class CrossCaseWitnessHit:
    """One hit for the cross-case-witness-conflict query — a person who
    appears on more than one case under different roles. The detective
    wants to know who's been a witness in one case and a suspect in
    another, etc."""
    person_id: str
    person_name: str
    appearances: list[dict[str, Any]]
        # each: {case_id, case_number, case_title, role, person_node_id, confidence}

    def to_dict(self) -> dict[str, Any]:
        return {
            "person_id": self.person_id,
            "person_name": self.person_name,
            "appearances": self.appearances,
        }


# ── ID helpers ────────────────────────────────────────────────────────────


def node_id(kind: NodeKind, raw_id: str) -> str:
    """Compose a graph-layer id. Always use this — never construct manually."""
    return f"{kind.value}:{raw_id}"


def split_node_id(nid: str) -> tuple[NodeKind, str]:
    kind_str, _, raw = nid.partition(":")
    return NodeKind(kind_str), raw
