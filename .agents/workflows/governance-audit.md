---
description: Run governance audit on memory bank, PRD, and project integrity
---

# /governance-audit

Verify that all governance rules, memory bank files, and PRD are in good shape.

## Steps

// turbo-all

1. **Check memory bank exists and is populated:**
   ```bash
   ls -la agents/memory-bank/lessons.md agents/memory-bank/current-state.md agents/memory-bank/invariants.md agents/memory-bank/module-registry.json
   ```

2. **Read `agents/memory-bank/invariants.md`** and verify none are violated.

3. **Read `agents/memory-bank/current-state.md`** — verify it matches reality:
   - Are completed items actually done?
   - Are "next" items still accurate?
   - Are blockers still blockers?

4. **Read `agents/memory-bank/module-registry.json`** — verify:
   - Module statuses match current-state.md
   - File lists are accurate
   - Dependencies are correct

5. **Read `docs/comprehensive-prd.md`** — verify:
   - All sections have content (not just headers)
   - PRD version matches changelog
   - Traceability matrix has entries for implemented features
   - "Prototype Limitations" section is present and accurate

6. **Check git status:**
   ```bash
   git status
   git log --oneline -5
   ```
   - No uncommitted changes to memory bank
   - Recent commits use conventional format with `[trace: ...]`

7. **Report findings** — list any violations, stale data, or missing content.

8. **Fix any issues found** — update memory bank and PRD as needed.

9. Commit fixes: `chore: governance audit fixes [trace: governance]`
