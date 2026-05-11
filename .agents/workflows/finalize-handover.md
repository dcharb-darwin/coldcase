---
description: Finalize handover package for dev team or customer delivery
---

# /finalize-handover

Create the complete handover package for customer review or dev team production build.

## Steps

1. Run `/regenerate-full-prd` to ensure PRD is fully up to date.

2. Run `/generate-demo-package` to ensure demo materials exist.

3. Create `docs/handoff-package/` directory.

4. Copy into handoff package:
   - `docs/comprehensive-prd.md` (the primary deliverable)
   - `docs/demo-instructions.md`
   - `docs/customer-review-script.md`
   - `docs/customer-review-package/media/` directory (screenshots)
   - All source discovery documents (markdown only)

5. Create `docs/handoff-package/README.md` with:
   - What this package contains
   - How to read the PRD
   - What the prototype code is (disposable POC)
   - Where to find the real requirements
   - Known limitations and open questions
   - Recommended tech stack for production

6. Create `docs/handoff-package/prototype-notes.md` with:
   - Architecture decisions and rationale
   - What shortcuts were taken for speed
   - What must be rebuilt properly
   - Security/auth considerations for production
   - Integration points and external dependencies

7. Commit: `docs: finalize handover package [trace: delivery]`
