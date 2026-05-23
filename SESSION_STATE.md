# Session State — Cold Case

**Last Updated:** 2026-05-22
**Last Session:** Multi-day continuation. Refactored CaseDetailPage 2,648 → 936 lines (tab extraction). Shipped multi-agent hypothesis flow (generator + de-novo + red-team) with closed-vocab bias flags. Added voice-capture brain dumps + Whisper-style transcription seam. Built graph service spine with NetworkX backend, four-dimensional edges (confidence / provenance / temporal / trust), plausibility scoring, officer identity-assertion override, node-link viz, and per-case + dashboard conflict panels. 26 commits, all on `origin/main`.

## Git identity + remote

- Remote: `git@github.com:dcharb-darwin/coldcase.git` (SSH).
- Identity for this app: **dcharb-darwin · daniel.charboneau@darwingov.com**.
- Always commit via `-c user.name= -c user.email=` flags — never `git config`.
- Every feat/fix commit ends with `[trace: <slug>]` and `Co-Authored-By: Claude Opus 4.7 (1M context)`.

## What's running now

```
docker compose ps     # mongo + backend + frontend, all bind-mounted to source for hot-reload
                      # ./dev.sh -d for detached, ./dev.sh --reset-db to nuke volume
```

Live URLs:
- Frontend: http://localhost:5178/
- Backend docs: http://localhost:7787/docs
- Mongo (host): localhost:27022 (volume `coldcase_mongo_data`)

Key endpoints to sanity-check the stack:
- `GET /launchpad/coldcase/api/admin/compliance/preflight` — 7-check report, `ready: true` when all pass
- `GET /launchpad/coldcase/api/graph/stats` — graph layer sizing (node/edge counts by kind)
- `GET /launchpad/coldcase/api/graph/cross-case-conflicts?mine=true` — Brady-risk conflicts after plausibility filtering
- `POST /launchpad/coldcase/api/demo/seed-plausibility` — synthetic test dataset (SYNTH-* cases)
- `bash scripts/compliance-smoke.sh` — 12-assertion end-to-end smoke

## What shipped this session (26 commits)

| # | Commit | Theme |
|---|---|---|
| 1 | `562aa3c` | refactor: extract PeopleTab from 2,648-line CaseDetailPage |
| 2 | `b549538` | refactor: extract BriefTab |
| 3 | `23acd9a` | refactor: extract TimelineTab |
| 4 | `2c6aba2` | refactor: extract ChainTab — orchestrator now under 1k lines |
| 5 | `fa28de7` | docs: tabs/ directory in STRUCTURE + SESSION_STATE |
| 6 | `fd8c896` | feat: dashboard cross-case insights panel |
| 7 | `7dbb799` | feat: AI extraction of unnamed references (Phase C closure) |
| 8 | `74c3e78` | fix: Save clue + Refresh UX (cards remove + emerald banner) |
| 9 | `6259912` | feat: likely-duplicate Person detection + merge |
| 10 | `2a8cc6d` | feat: brain-dump → AI hypothesis (Phase 0 + 1) |
| 11 | `1e9a97e` | feat: voice capture + audio upload + transcription seam (Phase 2) |
| 12 | `6331a4c` | docs: multi-agent hypothesis design doc |
| 13 | `8b2ae35` | feat: multi-agent — de-novo + red-team (v0.11.0) |
| 14 | `858b7ea` | feat: threaded notes (notes-on-notes) |
| 15 | `0b54451` | docs: graph layer design doc |
| 16 | `1197e8a` | feat: GraphService spine + NetworkX backend (v0.12.0) |
| 17 | `f99eb4d` | feat: dashboard cross-case role conflicts panel |
| 18 | `fb6876a` | feat: same-person plausibility scoring (3-signal composite) |
| 19 | `be5fbf5` | feat: synthetic plausibility-demo dataset + tightened cross-state penalty |
| 20 | `f1d2317` | feat: officer identity assertions (confirm same / mark different) |
| 21 | `91bda42` | feat: node-link graph visualization (9th tab, react-flow) |
| 22 | `27df840` | feat: per-case role-conflict panel on People tab |

## Current state — feature map

**Compliance backbone (§13663):**
- 7-check preflight, retention scheduler, first-AI-draft mutation deny, hash-chained audit (28+ event types)
- Agency policy template + vendor data-handling clause + compliance status doc
- AI provenance on Person + TagAssignment + Hypothesis + dedicated `*_ACCEPTED_FROM_AI` audit events

**Detective workspace (9 tabs + persistent chat):**
- **Brief** — stat cards · suggested next step (rule + AI) · key dates · connections · similar cases · grouped tags · AI tag suggester · threaded notes
- **Evidence** — docs + media + per-doc tags + citation jump
- **People** — role-grouped persons · AI extraction · cross-case lookup · mention finder · duplicate-merge banner · **per-case role-conflict banner**
- **Timeline** — manual + AI-extracted events + activity log
- **Hypothesis** — voice/upload/typed brain dump · multi-agent (generator + de-novo + red-team) · accept-each-individually · cross-check
- **Graph** *(new)* — react-flow node-link view of case neighborhood · confidence + depth sliders · pan/zoom/minimap
- **Reports** — list → full-route 3-column workspace
- **Chain** — live integrity card + per-report chain + case audit manifest PDF
- **Export** — discovery package + evidence.com data-readiness preview

**Graph layer (v0.12.0):**
- `services/graph/` package — interface + types + loader + NetworkX backend + backend factory
- Six query methods: case neighborhood, person across cases, person network, shortest path, cross-case role conflicts, stats
- Four edge dimensions on every edge: confidence (5-bucket vocab), provenance (8 sources), temporal (valid_from/to), trust (current/disputed/superseded)
- 60s TTL in-memory cache, invalidate on write
- Plausibility scorer (temporal × agency × distinctiveness) composes confidence on SAME_NAME_AS edges
- Officer identity assertions override the heuristic — CONFIRMED_SAME_PERSON_AS / CONFIRMED_DIFFERENT_PERSON_AS edges at 1.0 confidence
- Union-find clustering with assertion overrides (force-connect same / break different)
- Backend swap is one env var (`GRAPH_BACKEND=neo4j`); spine doesn't change

**Multi-agent hypothesis (v0.11.0):**
- Three agents: `generator` (brain-dump → hypotheses), `de_novo_generator` (case docs only), `red_team` (attacks one hypothesis)
- `services/bias_vocab.py` — closed 9-slug vocabulary so LLM can't invent flags
- HypothesisOrigin enum (human_typed / ai_from_braindump / ai_de_novo / ai_alternative) with parent linkage
- BrainDump model carrying audio_artifact_uri + transcript + provider lineage

**Synthetic dataset:**
- `seed/plausibility_demo.py` — 7 SYNTH-prefixed cases (KY 1985-2015, IN 1955, SC 2010), 19 persons, 2 hypotheses, 7 tag assignments
- Designed to exercise every plausibility branch: high (Marcus Webb 0.86), moderate (Diana Reeves 0.62), weak (John Williams 0.36 → can be Mark-different'd away), and coincidental cross-state/decade matches that are correctly hidden
- POST/DELETE `/demo/seed-plausibility` for idempotent seed + wipe

## Open / deferred work

- **Document chunking** — Passage as first-class node per `graph-layer.md`. Opens query 7 (mention cluster) + bigger-cases storyline.
- **Mongo `$graphLookup` backend** — for tenants past the in-memory ceiling (~100k nodes). Triggered when build time exceeds 5s.
- **Neo4j read replica** — for million-node tenants with heavy multi-hop pattern matching. Triggered only on real load.
- **Hypothesis events on Timeline tab** — surface status changes + red-team runs in chronological view.
- **Per-tenant bias-flag vocabulary override** — currently hard-coded in `bias_vocab.py`. Wait for a tenant ask.
- **Real GCC Copilot provider** — stub in `providers/llm.py`. Waits on agency Entra app.
- **Local Whisper transcription provider** — stub at `providers/transcription.py`. Wire `faster-whisper` once agency picks an on-prem model.
- **evidence.com integration** — auth + push deferred per user. Data shape is ready.
- **PRD §12 test-case statuses** — bump as features close.

## What to do at the start of the next session

1. Read this file + `docs/legal/compliance-status.md` (current statute posture) + `docs/design/graph-layer.md` + `docs/design/hypothesis-agents.md`.
2. `./dev.sh` (or `docker compose up -d` if the volumes are intact).
3. `bash scripts/compliance-smoke.sh` → expect 🟢 all assertions passed.
4. `POST /demo/seed-plausibility` → populate the synthetic dataset to exercise the graph layer.
5. Hit `/graph/stats`, `/graph/cross-case-conflicts?mine=true`, the dashboard, and a case's Graph tab to confirm everything renders.
6. Pick the next thread from the "Open / deferred work" section.

## Hard-won lessons from this session

- **`networkx.shortest_simple_paths` rejects MultiGraph.** Fold parallel edges to a plain Graph (keep best confidence per pair) before path-finding. The MultiDiGraph stores the original edges; the path-finding view is a flattened projection.
- **Cross-state penalty must be sharp enough to never bridge clusters via union-find.** A 0.3 penalty × 1.0 temporal × 1.0 distinctiveness = 0.30, which sneaks through a 0.25 threshold. Hardened to 0.15.
- **Build the dimensions before you can use them.** Shipped a four-dimensional edge model in the design doc but had the loader emit flat WEAK confidence everywhere — caught only after the user pointed at a 47-year cross-state false positive. Lesson: when you build a "multidimensional" model, write data-validation tests that ensure each dimension actually varies in production.
- **Hash-routed SPA doesn't re-render on hash change to the same path.** Two-step navigate (`/` then target hash) when changing case_id programmatically.
- **Synthetic data exposes bugs design review can't.** The plausibility scorer looked fine on the demo data because the demo had only 3 cases. Adding 7 carefully-designed synthetic cases immediately surfaced the cross-state-penalty hole. Build the dataset BEFORE shipping the filter.
- **TagAssignment uses `applied_by/applied_at`**, not `assigned_by/assigned_at`. Bit me when adding the loader.
- **`shortest_simple_paths` raises both `NetworkXNoPath` AND `NodeNotFound`** — catch both, return empty list.
- **react-flow's `@xyflow/react` package** (the maintained one, not the deprecated `reactflow`) is ~80KB gzipped and pulls in d3-* deps. Worth the cost for one viz; consider dynamic import if a second route doesn't need it.
- **Officer override edges (CONFIRMED_SAME / CONFIRMED_DIFFERENT) belong in the graph itself**, not in a filter on top. Let the union-find see them at clustering time — clean, no special-case branches.

## Worktree workflow (unchanged)

Worktrees live in `../coldcase.worktrees/`. To spin one up:
```
git worktree add ../coldcase.worktrees/<slug> -b feature/<slug>
```
Each worktree gets its own running stack via its own `./dev.sh`. Per-worktree `.env` can override the default port triplet.
