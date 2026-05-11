---
name: living-prd-updater
description: Maintain the comprehensive PRD by updating sections after module changes, tracing requirements to discovery
triggers:
  - update PRD
  - living PRD
  - documentation update
version: 1.0.0
---

# Living PRD Updater

## Overview
Keeps `docs/comprehensive-prd.md` current after every module change. Updates relevant sections, bumps version, adds changelog entry, and traces requirements to source documentation.

## When to Use
- After completing any module work
- After AntiDrift detects PRD staleness
- When `/update-living-prd <module>` is invoked

## Core Instructions
1. Read `agents/memory-bank/module-registry.json` to identify which PRD sections the module owns
2. Read the current PRD and identify sections needing updates
3. Update sections based on **actual implementation** (not planned — actual)
4. For every new requirement, add a row to the Traceability Matrix with:
   - Requirement description
   - Source document and section reference
   - Direct quote from discovery/source (if applicable)
5. Bump version (patch for content updates, minor for new sections)
6. Add changelog entry with date, module name, and changes
7. Verify "Prototype Limitations" section is still accurate

## Success Criteria
- PRD version matches changelog
- Every implemented feature has a traceability entry
- No section headers are empty after an update
- Prototype Limitations reflects current state
