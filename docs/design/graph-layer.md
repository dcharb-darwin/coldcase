# Graph layer — design doc

**Status:** Draft for review, 2026-05-20.
**Relates to:** [hypothesis-agents.md](./hypothesis-agents.md), workflow-and-ux.md §10.
**Prerequisite for:** node-link visualization, cross-case officer-reasoning analyzer, hypothesis-to-graph linkage, multi-hop "shortest path between two persons" query.

---

## Why this exists

The queries a cold-case detective actually wants today are not the queries we can write today.

We have a graph in our data — Person, Case, Document, Hypothesis, Tag, TimelineEvent are nodes; `appears_on`, `mentions`, `cites`, `contradicts`, `alternative_to`, `shares_tag_with` are edges. We've been building one-off endpoints for slices of it (1-hop connections on the Brief tab, 2-hop person network, Jaccard similar-cases, hypothesis alternative→parent linkage). Each new graph question becomes a new endpoint, a new MongoEngine query, a new shape of JSON. That doesn't scale, and worse, it prevents the queries the detective hasn't articulated yet.

Meanwhile the data volume question is real. A small-agency cold-case workload fits in memory trivially. A high-profile BTK-class case alone can be 5,000–50,000 nodes after decades of tips, witnesses, and document mentions. A mid-size county cold-case unit pushes 1M nodes tenant-wide. Today's stack handles the small case; we should design now so the big-case tenant doesn't force a rewrite later.

This doc is the architecture for getting both right: **flexible queries today, scale tomorrow, without paying for either prematurely.**

---

## Anti-patterns we're explicitly avoiding

| Anti-pattern | Why it bites |
|---|---|
| **Adopt Neo4j now, sync from Mongo** | Dual-write divergence is a discovery nightmare. The §13663(c) hash chain lives in Mongo. If the graph DB diverges, the city attorney can't answer "which artifacts produced this case decision?" without reconciling two stories. |
| **Hard-code Mongo aggregations in every endpoint** | When we eventually need real graph perf, every endpoint becomes a rewrite. Worse, the detective's mental model of "the graph" is fragmented across endpoint-specific JSON shapes. |
| **Treat every document as one node** | A 2,000-page case file shouldn't be one bullet point on a graph. We need passage-level addressability so "James M. Hinton mentioned at carter-pages-4-5.pdf line 17" is a distinct edge from "carter-page-7.pdf line 3". |
| **Boolean edges** | "X knows Y" is too coarse. We need confidence, provenance, time. An LLM-inferred relation at 0.4 confidence is not the same edge as a sworn-statement relation at 0.95. Traversal needs to know. |
| **Build the wrong queries first** | Visualization is sexy but it's not the query that solves cold cases. The query that solves them is "find the person who appears on multiple cases under different roles." Build the queries before the picture. |

---

## The interface — the load-bearing decision

Every graph query in Cold Case goes through one Python interface. Backends are interchangeable.

```python
# services/graph.py

class GraphService(Protocol):
    """Tenant-scoped graph view. Mongo is system of record; this layer
    is derived. Never persists; never replaces audit-chain operations."""

    def neighbors(
        self, node_id: GraphNodeId, *,
        edge_types: set[EdgeType] | None = None,
        depth: int = 1,
        min_confidence: float = 0.0,
        as_of: datetime | None = None,
    ) -> Subgraph: ...

    def shortest_path(
        self, source: GraphNodeId, target: GraphNodeId, *,
        edge_types: set[EdgeType] | None = None,
        max_hops: int = 5,
        min_confidence: float = 0.0,
    ) -> list[Path]: ...

    def find_pattern(self, pattern: GraphPattern) -> list[PatternMatch]: ...

    def subgraph_for_case(self, case_id: str, *, include_cross_case: bool = True) -> Subgraph: ...

    def cross_case_traversal(
        self, *, root_case_ids: list[str], depth: int = 2,
    ) -> Subgraph: ...
```

Three implementations behind this interface, picked at runtime by config:

| Backend | Class | When it wins | Limit before pain |
|---|---|---|---|
| **In-memory NetworkX** | `MongoNetworkXGraph` | Default for any tenant under ~100k nodes. Load whole tenant graph on first query, cache 60s. | ~100k nodes / 1M edges before build time exceeds 1s |
| **Lazy Mongo `$graphLookup`** | `MongoNativeGraph` | Per-query subgraph loading. Single neighborhoods scale to any tenant size. | Multi-hop pattern matching (path queries, triangle finding) gets expensive past 3 hops |
| **Neo4j read replica** | `Neo4jGraph` | Multi-million-node tenants, heavy pattern queries, big-case visualization. Backed by change-streams from Mongo. | Operational complexity; only worth it when one tenant clearly needs it |

The interface is the load-bearing decision. Anything else (Neo4j, ArangoDB, Memgraph, change-streams, async pre-computation) is implementation detail behind it.

---

## Node + edge model

Five node kinds match what we already persist. The graph layer doesn't introduce new entities; it provides a uniform view.

```python
class NodeKind(str, Enum):
    PERSON      = "person"
    CASE        = "case"
    DOCUMENT    = "document"
    PASSAGE     = "passage"      # subdivision of a document — see chunking below
    HYPOTHESIS  = "hypothesis"
    TAG         = "tag"
    TIMELINE    = "timeline_event"


class EdgeKind(str, Enum):
    # Person edges
    APPEARS_ON_CASE      = "appears_on_case"     # Person → Case
    MENTIONED_AT         = "mentioned_at"        # Person → Passage
    MERGED_INTO          = "merged_into"         # Person → Person (deleted duplicate)
    SAME_NAME_AS         = "same_name_as"        # Person → Person (loose match)
    CO_OCCURS_WITH       = "co_occurs_with"      # Person ↔ Person (on the same case)

    # Document edges
    CITES                = "cites"                # Document → Document (one references another)
    BELONGS_TO_CASE      = "belongs_to_case"      # Document → Case
    CONTAINS_PASSAGE     = "contains_passage"     # Document → Passage

    # Hypothesis edges
    ABOUT_CASE           = "about_case"           # Hypothesis → Case
    SUPPORTED_BY         = "supported_by"         # Hypothesis → Passage (kind=supporting)
    CONTRADICTED_BY      = "contradicted_by"      # Hypothesis → Passage (kind=contradicting)
    ALTERNATIVE_TO       = "alternative_to"       # Hypothesis → Hypothesis (red-team child)

    # Tag + similarity
    TAGGED_WITH          = "tagged_with"          # any-subject → Tag
    SIMILAR_VIA_TAG      = "similar_via_tag"      # Case ↔ Case (Jaccard)

    # Timeline
    EVENT_ON_CASE        = "event_on_case"        # TimelineEvent → Case
    REFERENCES_PERSON    = "references_person"    # TimelineEvent → Person
```

### Every edge carries four dimensions

This is what makes the graph "multidimensional" in the sense that matters to a detective — not the topology, but the properties on every link.

```python
@dataclass(frozen=True)
class Edge:
    kind: EdgeKind
    source: GraphNodeId
    target: GraphNodeId

    # 1. Confidence — how strong is the assertion?
    confidence: float  # [0.0, 1.0]

    # 2. Provenance — who or what asserted it?
    provenance: ProvenanceSource  # human_officer | ai_generator | ai_de_novo
                                  # | ai_red_team | derived_jaccard | derived_substring
    asserted_by: str   # user_id or model name
    asserted_at: datetime

    # 3. Temporal — when does the relation hold?
    valid_from: datetime | None
    valid_to: datetime | None       # None = still current

    # 4. Trust — has this been disputed?
    status: EdgeStatus  # current | disputed | superseded
    disputed_by: str = ""           # if status=disputed, who/why
```

The four dimensions are independently filterable in any query. "Show me Person↔Case edges asserted in the last year, by human officers, with confidence > 0.7, that haven't been disputed" is one call, not five.

### Confidence-scoring conventions (closed vocabulary)

To prevent every edge-emitting service from inventing its own scoring, we standardize. Closed list, like bias-flag slugs:

| Confidence range | Meaning | Examples |
|---|---|---|
| **0.95–1.00** | Officer-confirmed under oath / exact match | Officer signed report names this person, sworn witness statement, identical normalized name across cases |
| **0.80–0.94** | Officer-confirmed casually | Detective accepted an AI suggestion explicitly, manually entered with descriptor |
| **0.60–0.79** | High-confidence inference, multiple anchors | AI-generated hypothesis with multiple supporting excerpts, name + descriptor double-match |
| **0.40–0.59** | Single-source inference | AI-inferred mention with one source passage, single-initial name match |
| **0.20–0.39** | Weak inference | Loose name match without descriptor, generated alternative without supporting evidence |
| **< 0.20** | Speculative | Reject; don't emit the edge |

The number isn't precise — it's an honesty knob. Traversal queries default `min_confidence=0.4` so the speculative tail doesn't pollute output unless the user explicitly opts in.

---

## Document chunking — passages as first-class nodes

A 2,000-page case file collapsed to one node loses everything. We chunk every Document into Passage nodes.

### Chunking strategy

| Document type | Chunk unit | Why |
|---|---|---|
| **PDF with text layer** | 1 page per chunk if dense; paragraph if sparse | Page is the natural unit detectives cite ("see page 4-5") |
| **OCR'd PDF** | Page, with confidence score derived from OCR quality | OCR confidence flows into edge confidence on `mentioned_at` edges |
| **Plain text** | Paragraph (double-newline delimited) | |
| **Witness statement transcript** | Q&A turn | Detective cites by speaker turn, not page |
| **Bodycam transcript** | 30-second segment by timestamp | |

Each Passage carries:
- `document_id` — parent doc
- `ordinal` — passage index within doc (page 4, paragraph 2, segment 12)
- `excerpt` — the text itself (capped at 2KB for hot storage; full text on cold tier)
- `source_locator` — opaque "where in the document" string: "page=4", "paragraph=2", "timestamp=00:02:30"
- `text_confidence` — for OCR'd / transcribed sources; passthrough otherwise

A `Person → Passage` edge is what `mentioned_at` actually points to, replacing today's `getPersonMentions` substring-scan-on-demand approach. Edges accumulate over time; the substring scanner becomes one of several edge-emitters rather than the only path.

### Why this matters for big cases

A high-profile cold case has people who appear in passing across hundreds of pages. Without passage-level addressing, the detective sees "Person X mentioned in case file" — useless. With it, they see "Person X mentioned at carter-pages-4-5.pdf page 4 paragraph 2: '…borrowed rice from her aunt that day…'" — actionable. Same node, very different signal.

---

## Tier model — hot, warm, cold

Not every case needs to be in memory all the time.

| Tier | What lives there | Storage | Latency | Used when |
|---|---|---|---|---|
| **Hot** | Currently open cases for active users (per-tenant working set); current hypotheses; recent passages | In-memory graph (NetworkX) + Mongo | < 100ms | Default UI rendering |
| **Warm** | Closed cases under retention, archived hypotheses, older passages | Mongo only | 500ms–2s | Cross-case search, dashboard insights, similar-case Jaccard |
| **Cold** | Retention-expired but legally preserved | Object storage (blob), pulled on demand | 5–30s | PRA / discovery responses, never UI-blocking |

The tier is a property on the node, advanced by the retention scheduler:
- New cases start hot
- After 30 days closed with no access → warm
- After full retention timer + no access → cold (compressed, indexed-only)

Hot tier IS the in-memory graph. Warm tier requires a Mongo round-trip per query. Cold tier requires an explicit "expand archived material" affordance in the UI so detectives don't accidentally trigger a 30s spinner on dashboard load.

### Per-case neighborhood query stays fast at any tenant size

Crucial property: a per-case workspace only needs the case's neighborhood, not the whole tenant graph. Hot tier contains exactly what the detective is currently looking at. The full tenant graph never needs to be in memory at once.

---

## Backend implementations

### Today: `MongoNetworkXGraph`

Default. Loads tenant graph from Mongo on first query (1–3s for a small agency, cached for 60s). Subsequent queries are < 50ms. Traversals use NetworkX algorithms (shortest_path, BFS, pattern matching).

**Pros:** zero new infrastructure; full Python; arbitrary query expressivity; testable.
**Cons:** memory ceiling around 100k nodes; cache-staleness window.

Cache invalidation on writes is event-based, not time-based: a write to Person/Case/Hypothesis/Tag/Document bumps the tenant cache version, next read rebuilds.

### Medium scale: `MongoNativeGraph` via `$graphLookup`

Same interface, different implementation. Each `neighbors()` call becomes a `$graphLookup` aggregation. Multi-hop traversals are slower (each hop = an aggregation pipeline stage) but no memory ceiling. Pattern matching not directly supported — falls back to client-side filtering after a broad neighbor pull.

**Pros:** scales to millions of nodes; no cache to invalidate; uses existing Mongo cluster.
**Cons:** $graphLookup has surprising performance cliffs past 3-4 hops; pattern matching is awkward.

Migration trigger: tenant graph build time exceeds 5s OR memory of the graph service container exceeds 1 GB.

### Large scale: `Neo4jGraph` as read replica

Mongo remains system of record. A Mongo change stream feeds a Neo4j replica. Read queries hit Neo4j; writes still go through Mongo. The hash-chained audit stays in Mongo so §13663(c) review never depends on Neo4j integrity.

Cypher beats both other backends for multi-hop pattern matching (triangles, shortest path with edge weights, subgraph isomorphism). Neo4j Bloom or browser provides the visualization layer for free.

**Migration trigger:** specific tenant has hypothetical-but-not-yet-real performance need. Don't migrate preemptively. The first tenant who legitimately needs Neo4j gets it; everyone else stays on the simpler stack.

---

## Cross-cutting: audit + RBAC + tenant isolation

Three rules every backend implementation honors:

1. **Tenant scoping is non-negotiable.** Every query takes `tenant_id` as the first parameter. There is no global graph; there is the tenant's graph. Cross-tenant queries are explicitly forbidden at the interface — the type system prevents you from constructing one.

2. **RBAC at edge resolution.** A user with `case.read` on case A but not case B sees edges to case B as anonymized stubs (kind + classification, no title or person details). The graph layer asks the RBAC system per-edge during result construction; no full-graph access bypass.

3. **Audit-chain immutability.** The graph never writes back to Mongo. Edges derived from Mongo data don't create new audit events; the underlying Mongo writes already did. The graph is a *view*.

---

## Query catalogue — ranked by detective value

The interface is judged by whether these queries are easy. Listed in approximate order of expected daily-use frequency.

| # | Query | One-line description |
|---|---|---|
| 1 | **Case neighborhood** | "Show me everything connected to this case at depth 2" (already partially exists; unify under graph layer) |
| 2 | **Person across cases** | "Where else does this person appear?" (1-hop, exists; promote to confidence-filtered) |
| 3 | **Person network** | "Who else shows up with this person across cases?" (2-hop; exists, promote) |
| 4 | **Path between two persons** | "How are these two people connected through the case file?" (shortest path, max 5 hops, min confidence 0.4) |
| 5 | **Cross-case witness conflict** | "Find people who testified on multiple cases under different roles" (pattern: Person→Case[role=A] AND Person→Case[role=B] where A≠B) |
| 6 | **Suspicious co-occurrence** | "Find suspects who share an alibi witness" (pattern: two suspects, one witness, all on different cases) |
| 7 | **Document mention cluster** | "Show me passages across the whole case file that mention this person" (Person → Passage edges; passage-level addressing) |
| 8 | **Hypothesis lineage** | "Show me the family tree of hypotheses on this case" (Hypothesis → Hypothesis via `alternative_to`; tree rendering) |
| 9 | **Bias cluster** | "Find hypotheses across all my cases that share a bias flag" (Hypothesis nodes with overlapping `bias_flags`) |
| 10 | **Officer reasoning pattern** | "Find clusters of hypotheses by detective with high red-team challenge counts" (Hypothesis nodes filtered by `proposed_by` and `red_team_count`) |
| 11 | **Tag-similar cases** | "Cases sharing tag-vocabulary with this one" (already exists; unify) |
| 12 | **Cold trail revival** | "Find archived cases whose passage mentions match a current case's person list" (cross-tier; warms cold-tier material on detective demand) |

Each of these gets a thin endpoint that calls into `GraphService`. The endpoint validates inputs and renders JSON; all logic lives in the graph service.

---

## Visualization (deferred until interface lands)

A node-link visualization on the case workspace was sketched earlier and deferred for lack of a data layer. This is the data layer. UI follow-up will use a force-directed layout (d3-force or react-flow), constrained to a per-case neighborhood at depth 2 by default with a "expand" affordance per node.

Visualization is downstream of the queries — if queries 4 (path) and 5 (cross-case conflict) work as endpoints, the picture mostly draws itself.

---

## Open questions

1. **Where does the graph layer live in the code?** Vote: `server-py/services/graph/` as a package, with `interface.py`, `networkx_backend.py`, `mongo_native_backend.py`, `neo4j_backend.py` (last two not implemented day one). Provider picked via `GRAPH_BACKEND` env var, default `networkx`.

2. **Passage chunking — eager or lazy?** Eager (chunk on document register) makes mentions instant but bloats Mongo. Lazy (chunk on first traversal needing passages) defers cost. Vote: lazy, with a background sweeper that gradually eagerly-chunks documents on hot cases.

3. **Edge persistence — derive every time or materialize?** Today everything's derived (Person mentions via substring scan on demand; Jaccard computed at query time). For big tenants, derivation cost adds up. Vote: derive default; cache derived edges with TTL; materialize only after measurement shows a specific edge type is the bottleneck.

4. **`SAME_NAME_AS` edges across tenants?** Never. Cross-tenant edges violate the tenant-isolation rule. Each tenant's graph is fully isolated.

5. **Should the audit chain itself appear in the graph?** Tempting (it's the most authoritative edge set we have). Skip — audit events are point-in-time records, not present-tense relations. Surfacing them in the graph confuses the "what's true now" question. They stay in `AuditEvent` for review tools.

6. **Confidence calibration over time?** If we ship confidence buckets and the bucket boundaries turn out wrong, do we re-score? Vote: no automatic re-scoring. Edges keep the confidence they were emitted with. If we change the scale, document it in the changelog and let new edges use the new scale; old edges keep their old number with a `scale_version=1` marker.

---

## What ships in PR

One PR, label `feat: graph service interface + NetworkX backend`:

- `services/graph/interface.py` — Protocol + dataclasses
- `services/graph/types.py` — NodeKind, EdgeKind, Edge, Subgraph, Path, GraphPattern
- `services/graph/networkx_backend.py` — first implementation, loads tenant from Mongo on demand, 60s cache
- `routers/graph.py` — endpoints for queries 1–5 from the catalogue (the high-frequency set)
- Lifespan event-bumped cache invalidation hooks on Person / Hypothesis / Tag / Document writes
- Tests covering the interface contract — implementation-swappable

What's **out** of this PR:
- Passage chunking (queries 7, 12) — separate follow-up once first PR lands
- Visualization
- Mongo `$graphLookup` backend
- Neo4j backend
- Cross-tier (warm/cold) wiring
- Confidence calibration

These are the right things to defer because each is independently valuable AND independently sized. Ship the spine; add limbs as load demands.
