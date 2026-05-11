---
name: reviewer-gate
description: Standardized ReviewerAgent workflow for PRs, PRD changes, and module completions
triggers:
  - review PR
  - review gate
  - code review
  - PRD review
version: 1.0.0
---

# Reviewer Gate

## Overview
Standardized review workflow that the ReviewerAgent follows for every PR, PRD change, and module completion. Ensures no code merges without proper review.

## When to Use
- Before merging any PR to main
- After PRD updates (human review gate)
- At module completion checkpoints

## Core Instructions
1. **Code review checklist:**
   - [ ] Follows project stack (React 19 / FastAPI / MongoEngine / MongoDB)
   - [ ] Commit messages have `[trace:]` tags
   - [ ] No hardcoded values that should be configurable
   - [ ] MongoEngine models have `to_dict()` methods
   - [ ] API responses use consistent serialization
   - [ ] No raw hex/rgb colors in component files
   - [ ] Shared helpers used instead of duplicated logic
2. **PRD review checklist:**
   - [ ] Updated sections match implementation
   - [ ] Traceability matrix has new entries
   - [ ] Version bumped and changelog updated
   - [ ] Prototype Limitations still accurate
3. **Module completion checklist:**
   - [ ] All acceptance criteria for module are passing
   - [ ] Memory bank updated (current-state.md, module-registry.json)
   - [ ] AntiDrift audit passes clean
4. Flag any issues and require fixes before merge

## Success Criteria
- No PR merges without passing all applicable checklists
- Human approval required for PRD changes
- Issues are specific and actionable
