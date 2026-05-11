# Invariants — Cold Case

> Constraints that must never be violated. If you catch yourself about to break one, stop and check the rules doc it points to.

## Hard invariants (kit-wide)

1. **Ports come from `.env`.** Never hard-code a port in compose / vite / code. → `docs/PATTERNS.md` §6
2. **Launchpad Admin Pattern is verbatim.** Do not hand-edit `server-py/launchpad_admin/` or `src/launchpad-admin/`. Upstream changes propagate through the kit. → `docs/PATTERNS.md` §2, `ADR-002`
3. **Design tokens only.** No raw hex/rgb in component files. → `docs/PRINCIPLES.md` §P5
4. **JSON-mode for structured LLM output.** Never parse free-form responses. → `docs/PATTERNS.md` §3
5. **LLM is a translator, not an authorizer.** Every proposed action validates against the manifest before hitting the DB. → `docs/AGENTIC.md` §2
6. **Audit writes never block.** `services/audit.py::record` is fire-and-forget. → `docs/PATTERNS.md` §5
7. **`any` is banned in TypeScript.** Use `unknown` + narrow, or define the type. → `docs/CONVENTIONS.md`
8. **Commit trailer required** on every feat/fix/chore: `[trace: coldcase-<concern>]`. → `docs/CONVENTIONS.md`

## Soft invariants (this app's policies)

Add app-specific invariants below as they emerge. Examples:

- `Employee.ssn` never shown in UI.
- Audit retention: 7 years.
- PII boundary: no free-form notes fields.

## When you break one (the incident kind, not the forget-and-commit kind)

1. Stop.
2. Document what broke it (code + commit SHA) in `lessons.md` under a new heading.
3. Fix forward — a new commit that restores the invariant.
4. Never rewrite history to erase the violation.
