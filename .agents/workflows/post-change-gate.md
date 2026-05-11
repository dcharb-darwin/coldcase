---
description: Unified post-change verification gate. Run before every commit that touches application code. Combines change-impact checklist, verification, and traceability check.
---

# Post-Change Gate

**When to use:** Before committing ANY change to application code, config, or docs. The orchestrator owns this gate.

**Anti-pattern this prevents:** Committing code changes that silently break the build, leave docs stale, or miss `[trace:]` tags.

---

## Step 1: Determine Changed Files

// turbo
```bash
git diff --name-only HEAD
```

If no staged changes, use `git diff --name-only` for unstaged.

---

## Step 2: Impact Mapping — What Docs Need Checking?

| If changed... | Check these |
|---------------|-------------|
| `server-py/routers/*.py` | CLAUDE.md arch map, PRD API section |
| `server-py/models/*.py` | CLAUDE.md data model, PRD data model |
| `server-py/server.py` | CLAUDE.md arch map (new routers wired?) |
| `src/pages/*.tsx` | CLAUDE.md arch map, README features, walkthroughs |
| `src/components/**` | CLAUDE.md arch map components section |
| `src/lib/**` | CLAUDE.md arch map lib section |
| `src/index.css` | Brand tokens documentation |
| `package.json` | README tech stack, Docker build |
| `Dockerfile`, `docker-compose.yml` | Docker verify |
| `.agent/skills/**` | AGENTS.md Skills Library table |
| `.agents/workflows/**` | AGENTS.md Workflows list |
| Any UI/branding change | Customer walkthrough screenshots |
| Any feature add/remove | PRD feature table, walkthrough, README |
| Any code change | `current-state.md`, `lessons.md` if applicable |

---

## Step 3: Verification Tier

Determine the highest applicable tier:

| Tier | Trigger | Actions |
|------|---------|---------|
| **0 — Docs** | Only docs/memory/config | Impact checklist only, no build |
| **1 — App** | `src/**` or `server-py/**` | `npx tsc --noEmit` |
| **2 — Container** | `package.json`, `Dockerfile`, `docker-compose.yml` | Docker compose build + up + health + down |
| **2.5 — UI Smoke** | `src/pages/**`, `src/components/**`, `index.css` | Docker up → browser smoke test → Docker down |
| **3 — Integration** | Sync/integration files | Fullstack Docker + integration smoke tests |

---

## Step 4: Trace Check

Verify commit message includes `[trace:]` tag. If missing, add one before committing.

Format: `[trace: <source> §<section>]` — e.g., `[trace: AGENTS.md §3 — provenance]`

---

## Step 5: Report

Record what was checked:

```
Files changed: <count>
Verification tier: <0|1|2|2.5|3>
Impact docs checked: <list>
Docker verify: <run|skipped (reason)>
Trace tag: <present|added>
```

---

## Escape Hatch

Add `[skip-check]` to commit message to bypass advisory warnings. Must include a reason.
Example: `chore: fix typo in README [skip-check: docs-only] [trace: docs]`
