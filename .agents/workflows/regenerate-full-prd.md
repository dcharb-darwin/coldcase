---
description: Regenerate the full PRD from source documents and current codebase
---

# /regenerate-full-prd

Complete regeneration of `docs/comprehensive-prd.md` from source documents and current codebase.

## Steps

// turbo-all

1. Read all source/discovery documents in `docs/discovery/` (if they exist).

2. Read `agents/memory-bank/module-registry.json` to see module status.

3. Scan the codebase for current models/schema to generate accurate data model docs.

4. Regenerate every section in `docs/comprehensive-prd.md`:
   - Executive Summary
   - Full Requirements (traced to discovery/source quotes)
   - Data Model + diagrams (from MongoEngine models or schema)
   - Features & Flows (from dev plan + implemented code)
   - Acceptance Criteria
   - Prototype Limitations
   - Demo Instructions + Customer Review Script
   - Traceability Matrix (every requirement → source quote)
   - PRD Changelog (preserve existing log, add regeneration entry)

5. Bump PRD version and add changelog entry.

6. Commit: `docs: regenerate full PRD [trace: full-audit]`
