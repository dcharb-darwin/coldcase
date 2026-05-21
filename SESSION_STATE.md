# Session State — Cold Case

**Last Updated:** 2026-05-20
**Last Session:** Single-day pass: §13663 hardening + Phase A workspace + Phase B tags + Phase C AI extraction + hash-chained audit integrity + AI provenance + graph (1-hop, 2-hop, similar cases, document mentions) + CaseDetailPage refactor (2,648 → 936 lines via Brief/People/Timeline/Chain tab extraction). 15 commits, all pushed to `origin/main`.

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
- `GET /launchpad/coldcase/api/admin/compliance/audit-chain` — full chain verification
- `bash scripts/compliance-smoke.sh` — 12-assertion end-to-end smoke

## What shipped this session (11 commits on `main`)

| Commit | Theme |
|---|---|
| `4526479` | Phase A workspace shell (tabbed Brief/Evidence/Reports/Chain/Export) + §13663 hardening (preflight, retention scheduler, first-draft mutation deny, agency policy template + vendor data-handling clause + compliance status doc) + evidence.com data-readiness schema (Case/Doc/Media/Report external_id, agency_ori_snapshot, date_of_incident) |
| `7baeb61` | Phase C AI extraction: tag suggestions, person extraction, timeline-event extraction + polish (cross-route citation jump, report-subject tags, dashboard tag filter) |
| `8a4ba30` | Real hash-chained audit integrity — `sequence` + `prev_event_hash` + `event_hash` on every AuditEvent. Tamper-detection verified live |
| `67cf9bb` | Chain integrity card on Chain tab · Notes artifact (freeform detective scratch) · cross-case Person "↗ N other cases" chip |
| `68e8c2f` | State-aware Investigative-steps suggester on Brief tab (reads case docs + people + reports + tags + timeline) |
| `e36e991` | Formal AI provenance (`Provenance` embedded doc reused on Person + TagAssignment + audit events) + Case Connections graph (1-hop) |
| `d904b59` | Two-hop co-occurrence network ("who does this person share cases with") |
| `d52564c` | Similar cases (Jaccard over tags) + document mention finder (Person → exact doc + line) |
| `(this commit)` | Documentation consolidation: README rewrite + STRUCTURE update + SESSION_STATE refresh + PRD changelog |

## Current state — feature map

**Compliance backbone (§13663):**
- 7-check preflight at `/admin/compliance/preflight`
- Retention scheduler running daily (in-process asyncio task, `services/retention_scheduler.py`)
- First-AI-draft mutation deny + audit event
- Real hash-chained audit (715+ events on the live chain, 0 breaks, tamper-detection verified)
- Agency policy template (880 lines) + vendor data-handling clause + compliance status doc
- AI provenance on Person + TagAssignment + dedicated `*_ACCEPTED_FROM_AI` audit events

**Detective workspace (7 tabs + persistent chat):**
- Brief — stat cards · suggested next step (rule-based + AI investigative steps) · key dates · investigators · Connections (1-hop + 2-hop expand) · Similar cases (Jaccard) · grouped tags · AI tag suggester · Notes
- Evidence — docs + media + per-document tags + citation jump
- People — role-grouped persons with cross-case chip + mention finder (substring scan with variant matching)
- Timeline — manual + AI-extracted case events (colored dots by source) + activity log grouped by day
- Reports — list → full-route 3-column workspace with per-report tagging
- Chain — live integrity card + per-report chain cards + case audit manifest PDF
- Export — discovery package + evidence.com data-readiness preview

**AI surfaces** (all closed-vocab / grounded / accept-each-individually):
- Tag suggestions (vocab-constrained, can't invent slugs)
- Person extraction (with provenance + rationale)
- Timeline event extraction (date + label + source doc)
- Next investigative steps (state-aware — reads case state, not just doc text)

**Cross-case graph** (all derived, no new persistence):
- "Where else does this name appear?" (1-hop)
- Two-hop co-occurrence network ("who does this person know?")
- Tag-based similar cases (Jaccard)
- Document mention finder (substring scan with honorific/surname variants)

## Open / deferred work

- **evidence.com integration** (auth + push) — deferred. Data is shape-ready per `docs/design/workflow-and-ux.md §13`. When the agency provides Entra app + token model, the implementation is one new provider + ~10 lines of glue in `report_export.py`.
- **Real GCC Copilot provider** — stub in `providers/llm.py`. Awaits agency Entra app.
- **Person-mention extraction via AI** — substring finder is deterministic and works. AI mention extraction (broader than literal name match — pronouns, descriptions) would be a further Phase C step.
- **Visual node-link graph** — text-list Connections + Similar Cases panels are sufficient at current data volume. Worth revisiting when a tenant accumulates 10+ cross-case overlaps per case.
- **Per-doc + per-report Notes UI** — backend supports it; UI surfaces case-scope today (NotesPanel is scope-agnostic — zero-code addition when the UX calls for it).
- **PRD §12 test-case statuses** — should bump from ⏳ to ✅ where this session closed them (especially #2 — first-draft mutation 403).

## What to do at the start of the next session

1. Read this file + `docs/legal/compliance-status.md` (current statute posture).
2. `./dev.sh` (or `docker compose up -d` if you're sure the volumes are intact).
3. `bash scripts/compliance-smoke.sh` → expect 🟢 all assertions passed.
4. Hit `/admin/compliance/preflight` and `/admin/compliance/audit-chain` to confirm chain integrity.
5. Pick the next thread from the "Open / deferred work" section above, or whatever the agency sponsor surfaces.

## Hard-won lessons from this session

- **Tailwind v4 cascade trap:** the kit's `* { padding: 0 }` reset (and the `a { color: var(--color-primary) }` link rule) silently kill Tailwind utilities because v4 wraps them in `:where()` — same specificity loses on source order. Fix: wrap all bare-element rules in `@layer base`. This affects every Launchpad app — port the fix upstream.
- **BSON datetime precision:** `datetime.utcnow()` returns microseconds; MongoDB stores milliseconds. Any hash that includes a timestamp must truncate to ms precision at hash-time, or write-time hashes won't match read-time hashes. (Caught in `services/audit_chain.py`.)
- **Provenance is not the same as notes:** stuffing "Suggested by AI · …" into a detective-editable field looks fine until the detective edits the field and the lineage is lost. Provenance belongs in its own embedded doc with `source`, `model`, `rationale`, `accepted_by`, `accepted_at`.
- **Closed vocabulary matters for AI suggesters:** if the LLM can invent new tag slugs, the city attorney can't filter on them years later. Constrain the prompt to "only return slugs from this list" and validate the response against the same list.
- **Substring matching beats AI for literal name lookup:** document mention finder is deterministic, fast, and doesn't generate an audit event. Reserve the LLM for inference (who is mentioned that isn't named explicitly) — not for literal text search.

## Worktree workflow (unchanged)

Worktrees live in `../coldcase.worktrees/`. To spin one up:
```
git worktree add ../coldcase.worktrees/<slug> -b feature/<slug>
```
Each worktree gets its own running stack via its own `./dev.sh`. Per-worktree `.env` can override the default port triplet.
