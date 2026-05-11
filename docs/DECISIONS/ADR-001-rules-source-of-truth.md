# ADR-001: Rules source of truth lives in `docs/`, not in per-IDE entry files

- **Status:** Accepted
- **Date:** 2026-04-20

## Decision

The durable rules of a Launchpad app (design principles, architectural patterns, coding conventions, agentic behavior, lifecycle) live in five canonical markdown files under `docs/`:

- `docs/PRINCIPLES.md`
- `docs/PATTERNS.md`
- `docs/CONVENTIONS.md`
- `docs/AGENTIC.md`
- `docs/PLAYBOOK.md`

Per-IDE entry files (`AGENTS.md`, `CLAUDE.md`, `codex-instructions.md`, `.cursorrules`, `.windsurfrules`) are thin pointers to those five. They do **not** restate rules.

## Context

Pre-kit, every Launchpad app had rules duplicated across `AGENTS.md` + `CLAUDE.md` + `codex-instructions.md`. A rule change meant updating three files and hoping nothing drifted. Adding Cursor and Windsurf would have been a five-file update.

## Consequences

**Positive:** one file to edit per rule change. Agents in every IDE resolve to the same canonical doc. Drift between IDE entry files is impossible because they contain no rules.

**Negative:** agents have to follow a pointer to read the rules. A developer opening the repo in Claude Code for the first time reads `CLAUDE.md`, which says "read AGENTS.md first," which says "read `docs/PRINCIPLES.md`". Two hops.

**Mitigation:** the pointer files are short (< 50 lines) so the hops are cheap. The canonical docs are front-loaded with "read this first" callouts.

## Alternatives considered

- **Keep duplicating rules per IDE.** Rejected — drift is inevitable over months.
- **One mega-`AGENTS.md`.** Rejected — would become 1000+ lines across design + patterns + conventions + agentic + playbook, losing readability.
- **One per-rule file (e.g., `docs/ports.md`, `docs/naming.md`).** Rejected — too granular; rules cluster naturally into the five we picked.

## Revisit if

- A meaningful number of agents start ignoring `docs/` and only reading `AGENTS.md`. Then we'd need to consolidate.
- A new IDE shows up that can't follow a pointer. Unlikely.
