# Cold Case

A **governance + investigative workstation** for law-enforcement agencies using AI on cold-case files. Wraps the agency's GCC Copilot (or any LLM provider) with the audit trail California **Penal Code §13663 / SB-524** requires, plus a detective-first workspace that makes the AI useful for actual investigative work.

> **What it is:** a single web app where a detective opens a cold case, reads source documents, asks AI questions, accepts useful AI suggestions, drafts reports with the AI-as-first-author, signs them, and exports — with every prompt, response, edit, and signature preserved as tamper-evident audit chain that survives subpoena.
>
> **What it is NOT:** a replacement for evidence.com / records-management / the agency's existing storage. Source documents stay in the agency's Azure / S3. Cold Case stores metadata + lineage + signed artifacts.

---

## Two-minute pitch (for an agency sponsor)

1. **Detective opens a case.** Brief tab shows status, key dates, people on the case, server-computed system tags (`signed-report`, `discovery-exported`, `vendor-accessed`, `refusal-flagged`), and AI-suggested next investigative steps grounded in the actual case state.
2. **Asks the AI questions.** Chat panel scoped to the case's documents. Every prompt and response is logged with model id, in-context document ids, and a hash-chained audit event.
3. **AI proposes structure.** Tags from a closed agency vocabulary, named entities (suspects/witnesses/victims), dated timeline events — each with rationale. Detective accepts each individually; nothing is auto-applied. Accepted artifacts carry a formal AI provenance record (model + rationale + accepted_by + accepted_at).
4. **Detective promotes an AI answer to a report.** The original AI message becomes the immutable §13663(b) first draft. The detective edits, signs (e-signature with content hash), exports the PDF with the verbatim §13663(a)(1) disclosure on every page.
5. **City attorney audits.** Per-case audit-manifest PDF. Per-report chain-of-custody PDF. Live verifier walks the hash chain and reports any break.

Stand-up demo case (1945 Carter homicide, real declassified federal investigative records): every panel shows real data — Hinton's network, Letha Belle Carter as victim with AI provenance, the cross-doc mention lines, the report chain with `gpt-4o-mini-2024-07-18` identified.

---

## Compliance posture (CA Penal Code §13663 / SB-524)

| Statute requirement | Implementation |
|---|---|
| Agency policy on AI use [§13663(a) chapeau] | [`docs/legal/agency-policy-template.md`](docs/legal/agency-policy-template.md) — 880-line city-attorney-adoptable template |
| Verbatim disclosure on every report page [§13663(a)(1)] | `services/report_export.py` stamps the statutory string on every page of the exported PDF |
| AI program identification [§13663(a)(1)] | Exact dated model id (e.g. `gpt-4o-mini-2024-07-18`) captured at first-draft time, rendered on the disclosure footer |
| Officer signature attestation [§13663(a)(2)] | E-signature payload = user_id + display_name + timestamp + content SHA-256 + IP. Signer identity derived from authenticated session (F19) |
| First-AI-draft retention [§13663(b)] | Immutable; PATCH on a first-draft message returns 403 + `FIRST_DRAFT_MUTATION_BLOCKED` audit event. Retention scheduler preserves the floor on every sweep |
| Audit trail of every AI use [§13663(c)] | Every state change → AuditEvent. Per-tenant hash chain (sequence + prev_event_hash + event_hash) makes tampering detectable. Verified via `GET /admin/compliance/audit-chain` |
| Vendor data restrictions [§13663(d)] | `VendorAccessRequest` model + scope enforcement at runtime. Vendor data-handling clause at [`docs/legal/vendor-data-handling-clause.md`](docs/legal/vendor-data-handling-clause.md) |
| AI provenance on detective-accepted artifacts | New: every Person + TagAssignment + TimelineEntry + Note created from an AI suggestion carries source / model / rationale / accepted_by / accepted_at, with dedicated audit-event types (`PERSON_ACCEPTED_FROM_AI`, `TAG_ACCEPTED_FROM_AI`) |

**Deployment preflight** at `GET /admin/compliance/preflight` returns a 7-check report (auth bypass off in prod, LLM model in allowlist, agency letterhead populated, retention scheduler alive, vendor scope loaded, policy template shipped, audit chain integrity). `ready: true` only when all pass — runbook gates pilot go-live on this.

Live verified 2026-05-20: 738 events on the chain, 0 breaks. Tamper-detection test: mutating a single event's `summary` was caught at the exact sequence on the next verify call.

---

## The detective's workspace (case workspace tabs)

| Tab | What lives here |
|---|---|
| **Brief** | Stat cards (docs/reports/AI exposure) · suggested-next-step banner · AI-powered investigative steps suggester (state-aware: reads docs, people, reports, timeline) · key-dates vertical timeline · investigators · **Connections graph** (1-hop + 2-hop expand) · **Similar cases** (Jaccard over tags) · grouped tags (detective-applied + server-derived) · AI tag suggester · Notes (freeform scratch) · identifiers · description |
| **Evidence** | Documents + media sidebar · per-document text viewer with line numbers + citation jump · per-document tag bar (scope-filtered closed vocab) · extraction status badges (text / OCR / empty) |
| **People** | Role-grouped Persons (suspect / witness / victim / officer / POI / other) · manual add form · **AI entity extraction suggester** (proposes named people with role + descriptor + rationale) · per-person **cross-case "appears elsewhere" chip** + **mention finder** (substring scan across docs returning exact line numbers) |
| **Timeline** | "Case events" — detective-curated dated events (manual + AI-extracted with rationale + source doc) · activity log — every audit event grouped by day with color-coded dots |
| **Reports** | Drafts + signed reports list. Click → full-route report workspace (3-column: first-AI-draft / editor / citations + sign). Per-report tagging |
| **Chain** | **Live audit-chain integrity card** (event count, tip hash, breaks if any) · per-signed-report chain cards (mini event chain + AI program identifier + sha256) · case-wide audit-manifest PDF |
| **Export** | Discovery package generator · evidence.com data-readiness preview (integration deferred; metadata is shaped) |

Persistent chat panel on the right across every tab. Citations are clickable chips that jump to the cited doc + line via hash-route query (`?doc=…&line=…`).

---

## Cross-case investigative graph

| Surface | Question it answers |
|---|---|
| **"↗ N other cases" chip** on Person rows | "Where else does this name appear?" |
| **Connections panel** on Brief | "Who on this case has cross-case overlap?" |
| **+ network expand** on each Connections row | "Who does Hinton share cases with?" (2-hop co-occurrence) |
| **+ find document mentions** on Person rows | "Where in the actual documents is this name?" (line-by-line) |
| **Similar cases** on Brief | "What other cases share this tag set?" (Jaccard ranked) |

All derived / on-demand. No new persistence — the graph is always in sync with the underlying Person + Document + Tag data.

---

## AI surfaces

All four AI suggesters share a pattern: **closed vocabulary / grounded extraction / explicit accept-each-individually / formal provenance on accepted artifacts**. No auto-application.

| Surface | Endpoint | Constraint |
|---|---|---|
| Tag suggestions | `POST /cases/{id}/tags/suggestions` | LLM can only propose slugs from the agency's seeded vocabulary — never invent new tags |
| Person extraction | `POST /cases/{id}/persons/suggestions` | Returns name + role + descriptor + rationale; skips generic references; honors existing Person rows so it doesn't re-propose |
| Timeline event extraction | `POST /cases/{id}/timeline-entries/suggestions` | Date + label + notes + source doc + rationale; skips undated speculation |
| Next investigative steps | `POST /cases/{id}/next-steps/suggestions` | State-aware: reads case docs + people + reports + tags + refusal flags + timeline. Returns step + category + rationale grounded in a specific case fact |

Each accept call writes the provenance block and emits an `*_ACCEPTED_FROM_AI` audit event into the hash chain. City attorney can answer "which artifacts on this case came from AI?" with a single audit-event query.

---

## Stack

| Concern | Version |
|---|---|
| Frontend | React 19 · Vite 7 · Tailwind 4 · @tanstack/react-query 5 · axios 1 · TypeScript 5.7 |
| Backend | FastAPI 0.115 · MongoEngine 0.29 · Python 3.12+ · pydantic 2 · pydantic-settings 2 |
| Database | MongoDB 7 |
| LLM | Ollama (dev) · OpenAI (current) · GCC Copilot (stub) — provider seam at `server-py/providers/llm.py` |

## Ports

| Service | Default |
|---|---|
| Frontend | `5178` |
| Backend | `7787` |
| MongoDB | `27022` |

All env-driven via `.env`.

## Quick start

```bash
# one-time per clone
./scripts/install-git-hooks.sh

# bring up the stack (mongo + backend + frontend) via docker compose
./dev.sh
```

Open `http://localhost:5178/`. Demo data ships with the stack — load the synthetic 1992 Riverside Park homicide or the real 1945 civil-rights cold cases from the case-list buttons.

### End-to-end smoke

```bash
bash scripts/compliance-smoke.sh
```

Walks: case create → conversation → message → promote → first-draft mutation deny (verifies 403 + audit event) → sign → manual retention sweep → preflight (≥7 checks).

### Compliance verification endpoints

| Endpoint | Purpose |
|---|---|
| `GET /launchpad/coldcase/api/admin/compliance/preflight` | 7-check readiness report for pilot go-live |
| `GET /launchpad/coldcase/api/admin/compliance/audit-chain` | Full audit-chain verification (sequence gaps, prev-hash mismatches, recomputed-hash mismatches) |
| `POST /launchpad/coldcase/api/admin/compliance/audit-chain/rechain` | Admin-only repair (wipe + re-stamp) after evidence review |
| `POST /launchpad/coldcase/api/admin/retention/sweep?apply=false` | Dry-run retention sweep (always preserves first-AI-drafts) |

---

## Layout

See [`STRUCTURE.md`](STRUCTURE.md) for the directory tree and module-by-module map. Key entry points:

- Domain models: [`server-py/models/`](server-py/models/) (Case, Document, Message, Report, AuditEvent, Tag, TagAssignment, Person, TimelineEntry, Note, Provenance, VendorAccessRequest)
- Routers: [`server-py/routers/`](server-py/routers/) (one file per domain entity + admin_compliance + admin_retention)
- Hash chain: [`server-py/services/audit_chain.py`](server-py/services/audit_chain.py)
- Detective workspace: [`src/features/cases/pages/CaseDetailPage.tsx`](src/features/cases/pages/CaseDetailPage.tsx) (tab orchestration)
- AI provenance: [`server-py/models/person.py`](server-py/models/person.py) `Provenance` embedded doc — reused on Person + TagAssignment

## Documentation

| Doc | What's in it |
|---|---|
| [`docs/comprehensive-prd.md`](docs/comprehensive-prd.md) | Living PRD — features, business rules, §12 compliance matrix |
| [`docs/design/workflow-and-ux.md`](docs/design/workflow-and-ux.md) | UX strategy + phased plan + locked design decisions + evidence.com data-readiness appendix |
| [`docs/legal/sb524-text.md`](docs/legal/sb524-text.md) | Statute summary with verbatim quotes |
| [`docs/legal/compliance-status.md`](docs/legal/compliance-status.md) | City-attorney-readable gap assessment + pilot punch list (live-verified) |
| [`docs/legal/agency-policy-template.md`](docs/legal/agency-policy-template.md) | 880-line model policy for agency adoption |
| [`docs/legal/vendor-data-handling-clause.md`](docs/legal/vendor-data-handling-clause.md) | Contract clause aligned to §13663(d) carve-outs |
| [`AGENTS.md`](AGENTS.md) / [`CLAUDE.md`](CLAUDE.md) | Agent orchestration contract — every IDE / Claude Code respects |
| [`SESSION_STATE.md`](SESSION_STATE.md) | Rolling session handoff — current state, what's running, what's next |

## Identity

- Repo: `git@github.com:dcharb-darwin/coldcase.git`
- Commit identity: `dcharb-darwin <daniel.charboneau@darwingov.com>` (set inline via `git -c user.name=… -c user.email=…`)
- Every feat/fix commit ends with `[trace: <slug>]` and `Co-Authored-By: Claude Opus 4.7 …`

## Generated from

Scaffolded by [`launchpad-starter-kit v0.2.1`](~/Documents/Claude/Projects/hopkinsville/launchpad-starter-kit/). Retrofit workflow: [retrofit-existing-app.md](~/Documents/Claude/knowledge/launchpad/retrofit-existing-app.md).

**Important kit-side bug to port back:** Tailwind v4 + the kit's `* { padding: 0 }` reset silently nukes every padding utility. Fix is wrapping the reset in `@layer base` — see [`src/index.css`](src/index.css) at the cascade-fix comment. Every Launchpad app on the kit is currently affected.
