---
name: traceability-enforcer
description: Ensure all commits, PRD entries, and code comments trace back to source requirements
triggers:
  - trace
  - commit message
  - traceability
version: 1.0.0
---

# Traceability Enforcer

## Overview
Enforces that every change traces back to a requirement or design decision. Validates commit messages have `[trace:]` tags and PRD entries link to source documentation.

## When to Use
- Before every commit (pre-commit check)
- During AntiDrift audits
- When updating the PRD Traceability Matrix

## Core Instructions
1. **Commit messages:** Verify format `<type>(<scope>): <description> [trace: <ref>]`
   - `<ref>` can be: source document reference, PRD section, AGENTS.md section, or keyword
   - Example: `feat(models): add recording entity [trace: PRD §3.2]`
   - Example: `fix(auth): handle missing tenant [trace: lessons.md]`
2. **PRD entries:** Every requirement in the PRD must have a corresponding row in the Traceability Matrix with:
   - Source document and section reference
   - Direct quote from source (if applicable)
3. **Code comments:** Key business logic should have `// [trace: ...]` comments linking to design rationale
4. Flag any untraced commits or PRD entries

## Success Criteria
- 100% of commits have `[trace:]` tags
- PRD Traceability Matrix has entries for all implemented features
- No orphaned requirements (requirements without source backing)
