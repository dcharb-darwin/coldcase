---
name: browser-qa-smoke
description: Browser-based smoke test suite for UI verification after any frontend change
triggers:
  - After UI code changes (src/pages/, src/components/, src/App.tsx, src/index.css)
  - Post-change gate Tier 2.5
  - Before customer walkthrough recapture
version: 2.0.0
---

# Browser QA Smoke Test

## Overview
Automated browser-based smoke test using `browser_subagent` to verify core UI functionality after frontend changes. Project-agnostic — adapt the check list to your app's pages and routes.

## When to Use
- Post-change gate Tier 2.5 (any UI file change)
- Before capturing customer walkthrough screenshots
- After branding/styling changes
- After schema or API changes that affect displayed data

## Prerequisites
- App running (Docker or local dev server)
- Database seeded with test data

## Core Smoke Test Levels

### Level 1: Page Load (required — every UI change)
1. Navigate to app root — verify page loads without errors
2. Verify primary data list renders with seeded records
3. Verify navigation items are correct for the current mode

### Level 2: Interaction (required for component/page changes)
4. Click through all primary navigation tabs — verify content renders
5. Toggle any mode switches (e.g., MVP/Vision, admin/user) — verify UI updates
6. Navigate to secondary pages — verify they load
7. Toggle back — verify items revert correctly

### Level 3: Data Verification (required for schema/API/seed changes)
8. Verify key numeric fields are non-zero and formatted correctly
9. Verify list views show at least 1 record with expected fields
10. Verify status indicators/badges display with correct semantic colors
11. Verify health/alert indicators are present and styled per branding.md

### Level 4: Functional (run on feature changes or before demo)
12. Test search/filter functionality — verify results
13. Test import/upload UI — verify drag-drop or file picker renders
14. Test dark mode toggle — verify branding tokens apply
15. Test modal/form dialogs — verify they open, render fields, and close

## Browser Subagent Prompt Template

Customize the route URLs and page names for your project:

```
Navigate to http://localhost:5173 and perform the following smoke test.
For each check, report PASS or FAIL with a brief description.

CHECKS:
1. App root page loads and shows primary data list
2. At least [N] test records are visible
3. Click the first record — detail page loads
4. Detail view shows key data fields
5. Click through all tabs/sections
6. Toggle [any mode switch] and verify UI changes
7. Navigate to [secondary page] — page loads

Take a screenshot after checks 2, 4, and 7.
Return: list of PASS/FAIL for each check, plus any visual issues noticed.
```

## Failure Protocol
- L1 fail → **STOP** — app is broken, fix before continuing
- L2 fail → investigate specific component, may be non-blocking
- L3 fail → check API/seed data, likely backend issue
- L4 fail → log issue, proceed if not demo-blocking
