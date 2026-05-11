---
description: How to maintain session state for continuity across app restarts and agent sessions
---

# Session Handoff Workflow

When working on a multi-phase project, maintain a `SESSION_STATE.md` file in the project root so any new conversation can pick up immediately.

## When to Update

Update `SESSION_STATE.md` at:
1. The end of each significant work session
2. Before any known app restart
3. After completing a major phase or milestone
4. Before switching agents or tools

## File Format

```markdown
# Session State — [Project Name]
**Last Updated**: [timestamp]
**Last Conversation**: [conversation ID]

## Current Phase
[What phase/step we're actively working on]

## Just Completed
[What was finished in the last session]

## Next Steps (Priority Order)
1. [Immediate next task]
2. [Following task]
3. ...

## Blockers / Known Issues
- [Any blocking issues]

## Key Files Modified Recently
- [file paths]

## Running Services
- [Any services that should be running, ports, etc.]

## Environment Notes
- [Venv location, node version, etc.]
```

## On Resume

When the user says "continue" or "pick up where we left off":
1. Read `SESSION_STATE.md` from the project root
2. Read `agents/memory-bank/current-state.md` for broader context
3. Verify the current state matches what's documented
4. Continue from the documented next steps

## Anti-Drift Integration

At session end, also trigger the anti-drift auditor:
1. Verify memory bank freshness
2. Check that `current-state.md` aligns with `SESSION_STATE.md`
3. Verify PRD accuracy against implemented modules
4. Log any findings to `agents/memory-bank/lessons.md`
