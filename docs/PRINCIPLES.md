# Darwin Launchpad — Design Principles

> Source of truth for design intent. Every Launchpad app follows these. Every IDE (Claude Code, Cowork, Codex, Cursor, Windsurf) should read this file before generating UI.
>
> Drawn from `Launchpad_Design_Principles.docx` + the proven implementations in SOP Builder, HR Coordinator, Crew Scheduler.

## Part 1 — UX & Interaction

### P1. Everything visible is actionable

Every icon, badge, number, avatar, stat card drills into relevant context. No dead-end elements.

**Implementation.** Stat cards on a dashboard are clickable links to the roster filtered by that metric. Status badges on a row open the context that produced the status. Avatar in the top bar opens account / impersonation.

**Audit tool.** A Claude Code skill `p1-audit` (installed at `~/.claude/skills/p1-audit/`) scans any Launchpad app for P1 violations — dead-end numbers, badges, avatars, stat cards that look tappable but aren't. Invoke during PR review on UI changes, before a customer demo, or whenever you're asked "are all our clickable-looking things wired." Skill reports findings; you decide which to fix.

### P2. Cards + list toggle

The rule is asymmetric: **if a collection is presented as cards, it must also offer a list/table view**, with a toggle that persists across sessions. The reverse does not hold — a list/table-only surface is fine, because tables are already dense and adding cards would be cosmetic.

Rationale: cards optimize for one record at a time (visual, rich). Users scanning many records need a dense table fallback. Lists don't create the same pressure, so a list-only presentation satisfies P2 by default.

HR Coordinator's Pipeline view demonstrates the full both-ways pattern — same data renders as a dense table for the oversight persona, cards for the per-hire persona. That level of flexibility is optional; the floor is "cards ⇒ list toggle."

### P3. Consistent navigation shell

All authenticated surfaces share one layout wrapper:

- **Collapsible left nav rail** (`--nav-width` / `--nav-width-collapsed`, persisted in localStorage)
- **Fixed top bar** (`--topbar-height` 56px) with app identity, breadcrumbs, notifications affordance, user/avatar
- **Breadcrumbs** reflect route depth (Dashboard → Employees → Employee {name})
- **Impersonation banner** renders above the shell when an SA is impersonating another user

Reference implementation: `src/shell/AppShell.tsx` in the template.

### P4. Progressive disclosure

Dashboard is the primary landing. Detail screens are drill-downs reached from the shell (nav or in-content links), not isolated pages with only ad-hoc "Back" actions. Complexity revealed in layers — summary first, drill-down on interaction.

### P5. Consistent design tokens

All color, spacing, typography, shadow, animation values come from the shared token set declared in `src/index.css`. No raw hex / rgb values in component files. The token set is shipped in the kit and ships **byte-for-byte identical** to every Launchpad app so cross-app visual drift is impossible.

Token families:
- `--color-*` — semantic (background, surface, border, text, text-secondary, text-muted, primary, danger, success)
- `--space-*` — xs / sm / md / lg / xl
- `--radius-*` — sm / md / lg
- `--shadow-*` — sm / md / lg
- `--transition-*` — fast / base / slow
- `--nav-width`, `--nav-width-collapsed`, `--topbar-height`

### P6. Action confirmation for irreversibles

Destructive actions (delete, publish, terminal state changes) require an explicit confirm step — either a `confirm()` prompt for POC or a modal for production. The user can always see what will happen before it happens.

## Part 2 — Agentic behavior

These principles describe **how AI assistants inside a Launchpad app behave**, not how developer-side agents author the app. The developer-side rules live in `CONVENTIONS.md` and `AGENTIC.md`.

### A1. AI assistant surface is discoverable

If an app has an AI assistant (permission assistant, SOP finder, scheduler recommender), it has a dedicated surface. No hidden slash commands. The assistant is a nav item or a clear call-to-action on the relevant page.

### A2. Proposals are reviewable

Every action an AI proposes is rendered as a card with an explicit **Apply** button. No auto-apply. No background writes. The human is always in the loop.

### A3. Two-stage proposer → reviewer for high-stakes actions

Permission changes, terminal state transitions, bulk operations run through the proposer+reviewer pattern (see `AGENTIC.md` §2). The proposer drafts; the reviewer critiques; the UI shows both verdicts side by side.

### A4. Clarifying questions when prompts are ambiguous

If an assistant can't decide between two reasonable readings of a prompt, it asks rather than picks. The UI surfaces the clarifying question as a proposed-action card with type `clarification`.

### A5. Structured output, not free-form

Every AI response that influences app state is structured JSON validated against a schema defined in code. The LLM is a translator, not an authorizer. No permission string or action name gets to the DB without passing through validation that would have caught a hallucinated value.

## How these principles reach agents

- IDE entry files (`CLAUDE.md`, `AGENTS.md`, etc.) reference this file directly. They do not re-state the principles.
- Each Launchpad app ships an identical copy of this file at `docs/PRINCIPLES.md` (or references the kit's copy, depending on mode).
- Code review workflows (`reviewer-gate` skill, `post-change-gate` workflow) check generated UI against these principles.

## Not goals

- **Visual prescription** (exact pixel grid, exact typography). Tokens define those; this document names the principles that the tokens encode.
- **Per-app customization**. Principles are universal across Launchpad. Per-app branding lives in `docs/branding.md` and touches colors + logo only.
- **Agentic patterns for development-time assistance**. Those live in `CONVENTIONS.md` + `AGENTIC.md`.
