# IDE-Agnostic Wiring

How the Launchpad rules reach every development IDE / agent framework.

## The core move

**Rules live once.** In `docs/PRINCIPLES.md`, `docs/PATTERNS.md`, `docs/CONVENTIONS.md`, `docs/AGENTIC.md`, `docs/PLAYBOOK.md`.

**Per-IDE entry files are thin pointers.** They tell each tool's agent to read those five. They do not restate rules. This is the only way to keep rules in sync across five entry points without manual update of five files on every change.

## The five entry points

| IDE / Tool | Entry file | What it contains |
|---|---|---|
| Claude Code | `CLAUDE.md` | "Read AGENTS.md first. Then `docs/PRINCIPLES.md` etc. Architecture map for this repo." |
| Cowork | `AGENTS.md` | Master orchestration. Lists workflows, skills, gating rules. References the docs/. |
| Codex | `codex-instructions.md` | Symlink to `CLAUDE.md`. |
| Cursor | `.cursorrules` | "Follow AGENTS.md. See docs/PRINCIPLES.md for design." |
| Windsurf | `.windsurfrules` | Same as `.cursorrules`. |

All five resolve to the same five canonical docs.

## Why AGENTS.md instead of CLAUDE.md as the master

`AGENTS.md` is a convention **supported by multiple tools** (Cowork, Cursor, Windsurf honor it; Claude Code reads it when present). `CLAUDE.md` is Claude-specific. Making `CLAUDE.md` the master would leave the other tools looking at a file named for a single vendor.

Structure:
- `AGENTS.md` → the orchestration contract (no rules, just "here's how to work in this repo: follow the docs, use the workflows, commit with trailers")
- `CLAUDE.md` → claude-specific extras (architecture map + skill invocation hints) + "read AGENTS.md first"
- `.cursorrules` / `.windsurfrules` → 20-line pointers that say "follow AGENTS.md"

## Workflows and skills

`.agents/workflows/*.md` and `.agent/skills/*/SKILL.md` are **plain markdown procedures**. Any agent can execute them by reading steps. No Claude-only syntax is required in the procedure body.

Skill frontmatter (`name`, `description`, `license`) is Claude Code's mechanism for registering skills. Other tools ignore the frontmatter and read the procedure. The procedure works in either.

## Per-IDE config

Tool-specific configuration (not rules) lives in tool-specific directories:

- Claude Code: `.claude/settings.json`, `.claude/launch.json` — gitignored by default; commit only when the config is a repo-wide convention (e.g., a launch config everyone on the team should have).
- Cursor: `.cursor/*` — same treatment.
- Windsurf: `.windsurf/*` — same.

The kit does not prescribe settings. If a team adopts a shared Claude Code hooks configuration, document it in `docs/PLAYBOOK.md` and commit the file.

## What lives in each file — concrete

### AGENTS.md

```markdown
# AGENTS

Master orchestration contract. Read this first. Every agent that works in
this repo must follow these rules.

## Mandatory init sequence

1. Read `docs/PRINCIPLES.md` — design intent
2. Read `docs/PATTERNS.md` — architectural patterns
3. Read `docs/CONVENTIONS.md` — coding conventions
4. Read `docs/AGENTIC.md` if touching AI assistant code
5. Read `docs/PLAYBOOK.md` for lifecycle procedures
6. Read `agents/memory-bank/current-state.md` for module status
7. Read `SESSION_STATE.md` if continuing prior work

## Workflows

Use `.agents/workflows/<name>.md` procedures verbatim. Never skip a
post-change-gate or finalize-handover step.

## Skills

`.agent/skills/<name>/SKILL.md` procedures can be invoked for specific
tasks (anti-drift audits, reviewer gates, demo packaging).

## Commit contract

Every commit: `[trace: <slug>-<concern>]`. Git identity:
`dcharb-darwin <daniel.charboneau@darwingov.com>`.
```

### CLAUDE.md

```markdown
# CLAUDE.md

Claude Code-specific entry point. **Read `AGENTS.md` first.**

## Architecture map

[app-specific map pointing at server-py/, src/, docs/architecture.md]

## Skills available

- `architecture-diff-gate` — regenerate docs/architecture.md
- [other app-specific skills]
```

### .cursorrules / .windsurfrules

```
Follow AGENTS.md at the repo root. Read `docs/PRINCIPLES.md`,
`docs/PATTERNS.md`, and `docs/CONVENTIONS.md` before generating UI or
code. Commit trailers `[trace: <slug>-<concern>]` required.
```

## When an IDE needs a new capability

Four questions in order:
1. Can this be solved by editing one of the five canonical docs? → do that.
2. Can this be solved by adding a workflow or skill? → do that.
3. Is this an IDE-wide feature (e.g., Claude Code hooks)? → update the IDE's entry file and document in `docs/PLAYBOOK.md`.
4. Only-if-all-else-fails: add a new IDE-specific file.

The kit resists option 4. Three years of drift across five IDE entry files is the failure mode we're avoiding.

## What we're explicitly not doing

- **IDE auto-detection**. No scripts that sniff which IDE is running.
- **Conditional rules** (e.g., "this rule for Cowork only"). If a rule applies, it applies everywhere.
- **IDE-specific skill variants**. One skill, one procedure, every tool reads the same.

## Testing the IDE coverage

When you change a canonical doc, spot-check each IDE picks it up:
- Claude Code: open the repo, ask "what are this app's design principles?" — answer should cite `docs/PRINCIPLES.md`.
- Cursor: same.
- Cowork: same.

If an IDE doesn't cite the right doc, its entry file has a broken pointer — fix the pointer, not the rule.
