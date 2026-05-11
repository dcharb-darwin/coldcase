---
name: demo-package-generator
description: Generate demo screenshots, instructions, customer review script, and handover materials for stakeholder presentations
triggers:
  - demo package
  - generate demo
  - customer review
  - handover
version: 1.0.0
---

# Demo Package Generator

## Overview
Creates a complete demo package for presenting the prototype to stakeholders. Includes step-by-step instructions, screenshots, and a customer review script with validation questions.

## When to Use
- After MVP milestone is demo-ready
- After feature milestone is demo-ready
- When `/generate-demo-package` workflow is invoked

## Core Instructions
1. Create `docs/demo-instructions.md` with startup steps and feature walkthrough
2. Capture screenshots of key screens using browser tools into `docs/customer-review-package/media/`
3. Create `docs/customer-review-script.md` with:
   - Opening framing (2 min)
   - Per-screen validation questions for each stakeholder
   - Areas where feedback is needed
   - Closing questions
4. Include talking points: "Here's YOUR data / workflow"
5. Update PRD Demo Instructions section

## Success Criteria
- Demo instructions cover every implemented feature
- Screenshots exist for all key screens
- Customer review script has specific validation questions per stakeholder
- All media files are in `docs/customer-review-package/media/`
