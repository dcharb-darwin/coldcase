---
name: anti-drift-auditor
description: Run governance checks to detect drift from requirements, invariant violations, and stale documentation
triggers:
  - anti-drift
  - governance audit
  - drift check
  - run-anti-drift-audit
version: 1.0.0
---

# Anti-Drift Auditor

## Overview
Periodic and event-triggered governance auditor. Checks that the project hasn't drifted from requirements, invariants are intact, and documentation reflects reality.

## When to Use
- Every 30 minutes of active development
- After 10 tool calls in a session
- At every handoff between agents or sessions
- At session end (before updating SESSION_STATE.md)
- Before any merge to main
- Manual: `/run-anti-drift-audit`

## Core Instructions
1. **Memory bank consistency:** Verify all files in `agents/memory-bank/` exist and aren't stale (>24h without update during active development)
2. **Invariant compliance:** Read `agents/memory-bank/invariants.md`, verify each rule holds
3. **PRD accuracy:** Compare `docs/comprehensive-prd.md` sections against `agents/memory-bank/module-registry.json` — completed modules must have populated PRD sections
4. **Commit traceability:** Check last 10 git commits for `[trace:]` tags
5. **Module registry accuracy:** Verify module statuses match filesystem reality
6. **Skills library integrity:** Verify all required skill folders have valid `SKILL.md` files
7. If drift detected: propose specific rewind action with human confirmation required
8. Log findings to `agents/memory-bank/lessons.md`

## Success Criteria
- All 6 checks pass without findings = "CLEAN"
- Any finding produces a specific, actionable recommendation
- Never auto-fixes without human confirmation
