---
description: Generate a demo package for customer review or stakeholder walkthrough
---

# /generate-demo-package

Create a complete demo package for presenting the prototype to stakeholders.

## Steps

1. Create `docs/demo-instructions.md` with:
   - How to start the dev server
   - Step-by-step walkthrough of each feature
   - What to show each stakeholder and why
   - Talking points for each screen

2. Create `docs/customer-review-package/media/` directory.

3. Use the browser tool to navigate through the running app and capture screenshots of:
   - Landing/list view
   - Detail view with key relationships
   - Key workflow flows
   - Admin/settings surface
   - Any status/health indicators

4. Create `docs/customer-review-script.md` with:
   - Opening framing (2 min)
   - Per-screen validation questions for each stakeholder
   - Areas where feedback is needed
   - Features to validate against acceptance criteria
   - Closing questions: "What's missing?", "What would you change?", "Scale of 1-5?"

5. Update `docs/comprehensive-prd.md` Demo Instructions section.

6. Commit: `docs: generate demo package [trace: customer-validation]`
