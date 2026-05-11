---
name: branding-enforcer
description: Verify design system and brand consistency — CSS variables, color tokens, typography, dark mode
triggers:
  - branding check
  - design system audit
  - style drift
  - brand enforcement
version: 1.0.0
---

# Branding Enforcer

## Overview
Prevents brand/styling drift by verifying all colors, fonts, and dark mode tokens use the project's design system. Catches Tailwind escape hatches, raw hex/rgb values, and inconsistent semantic colors.

## When to Use
- Post-change gate: any change to `src/index.css`, component files, or `tailwind.config.*`
- After any branding/styling change
- Periodic audit via anti-drift-auditor

## Prerequisites
- Project must define design tokens in `docs/branding.md` or `src/index.css` (CSS custom properties)

## Core Checks (3 total)

### Check 1: No Color Escape Hatches
Grep component files for raw Tailwind dark-mode color overrides:
```bash
grep -rn "dark:bg-\[" src/ --include="*.tsx" --include="*.jsx" --include="*.ts"
grep -rn "dark:text-\[" src/ --include="*.tsx" --include="*.jsx" --include="*.ts"
```
**Pass:** Zero matches. All dark mode colors use CSS variables.
**Fail:** Any match → replace with `dark:bg-[var(--token)]` pattern.

### Check 2: CSS Variable Usage
Verify all color values in component files reference CSS custom properties:
```bash
grep -rn "bg-[a-z]*-[0-9]" src/ --include="*.tsx" --include="*.jsx" | grep -v "bg-white\|bg-black\|bg-transparent\|bg-inherit"
```
**Pass:** Zero matches (or only whitelisted neutrals).
**Fail:** Raw color classes found → replace with design token references.

### Check 3: Semantic Status Colors
Verify status indicators use consistent semantic tokens:
- Success/healthy → brand success token (not hardcoded green)
- Warning/at-risk → brand warning token (not hardcoded yellow/orange)
- Danger/error → brand danger token (not hardcoded red)
- Info/neutral → brand info token (not hardcoded blue/cyan)

```bash
grep -rn "text-green\|text-red\|text-yellow\|bg-green\|bg-red\|bg-yellow" src/ --include="*.tsx"
```

## Success Criteria
- All 3 checks pass = CLEAN
- Any failure → specific file:line with fix instruction
- Never auto-fixes — reports only

## Integration
- Referenced by `anti-drift-auditor` during periodic audits
- Referenced by `post-change-gate` when UI files change
- Add to `invariants.md`: "All colors via CSS custom properties. No raw color values except in design token definition."
