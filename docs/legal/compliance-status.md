# SB-524 / Penal Code §13663 — Compliance Status & Gap Assessment

**Document owner:** Cold Case engineering · **Reviewers:** Agency CIO, City Attorney
**Last verified against code:** 2026-05-20 (commit at top of `main`)
**Statute effective:** 2026-01-01 — **already in force.** Any agency that has detectives using GCC Copilot today is operating under §13663 obligations whether or not they have tooling in place.

> This document answers two questions, for a non-engineering reader:
> 1. **What does §13663 require an agency to do?**
> 2. **For each requirement, where is Cold Case today, and what is still open before a pilot agency can go live?**
>
> For the statute text, see [`sb524-text.md`](./sb524-text.md). For row-by-row engineering detail, see PRD §12 in [`../comprehensive-prd.md`](../comprehensive-prd.md).

---

## 1. Plain-English summary of what §13663 requires

| # | The agency must… | Why it exists |
|---|---|---|
| 1 | **Have a written policy** that covers AI-assisted reports (the §13663(a) "chapeau"). | Statute presumes the policy exists; tooling alone is not compliance. |
| 2 | **On every AI-assisted report, print the verbatim disclosure** "This report was written either fully or in part using artificial intelligence." **and identify the AI program(s) used.** [§13663(a)(1)] | Reader of the artifact must be on notice that AI was involved and which system. |
| 3 | **The officer signs the final report** (physical or electronic) attesting they reviewed it and that the facts are true and correct. [§13663(a)(2)] | The officer — not the AI — is accountable for the content. |
| 4 | **Retain the first AI draft for as long as the official report is retained**, and never treat it as the officer's statement. [§13663(b)] | Preserves the "before officer editing" baseline so defense / DA can see what AI generated. |
| 5 | **Maintain an audit trail** identifying (c)(1) the person who used AI and (c)(2) any video/audio used as input. [§13663(c)] | Every AI use must be traceable to a specific human and the source media. |
| 6 | **Bind AI vendors contractually and operationally** so vendor cannot share/sell/use agency data except to deliver the contracted service, comply with a court order, or improve the system. [§13663(d)] | Prevents an AI vendor from monetizing or leaking case data. |

The statute is short. The compliance burden lives in the *consistency* of doing those six things on every single AI-assisted report, forever, with an audit trail strong enough to survive subpoena.

---

## 2. Where Cold Case stands today — per requirement

Legend: **✅ Shipped & verified** · **🟡 Shipped, not pilot-hardened** · **❌ Not yet built**

### Req 1 — Written agency policy

- **Status: ❌**
- **Where it would live:** `docs/legal/agency-policy-template.md` (not yet drafted).
- **What's missing:** a model policy the agency's city attorney can adopt with minimal edits. Should cover: which officers may use AI, scope of permitted AI use (drafting / summarization / penal-code lookup), required training, mandatory first-draft preservation, vendor approval process, audit cadence.
- **Pilot blocker?** **Yes.** §13663(a) reads "*Each law enforcement agency shall maintain a policy…*" — the agency owns this artifact; Cold Case can provide the template but cannot substitute for it.

### Req 2 — Disclosure text + AI program identification on the report

- **Status: ✅**
- **Evidence in code:**
  - `services/report_export.py` stamps the verbatim disclosure on **every page** of the exported PDF.
  - `Report.ai_programs_used[]` is populated from the first-draft Message's `model` field, which captures the exact provider-returned model id (e.g. `gpt-4o-mini-2024-07-18`) — not a configured alias.
  - Smoke test extracts text from every rendered page with `pypdf` and asserts both the disclosure string and an AI-program name are present (PRD §12 test case #1).
- **Caveat:** disclosure is on the **Cold Case** PDF export. If the agency also publishes the Copilot raw output through evidence.com directly, that artifact must carry the disclosure too — out of scope for Cold Case today (see Req 2 follow-up below).

### Req 3 — Officer signature attestation

- **Status: 🟡 — shipped, hardened in F19, still needs a real identity provider in production**
- **Evidence in code:**
  - `POST /reports/{id}/sign` is required before `POST /reports/{id}/export` will succeed (returns 422 referencing §13663(a)(2) otherwise — smoke test case #3).
  - F19 fix: signer identity (`display_name`, `user_id`) is derived from the authenticated `UserContext`, **not** the request body. The detective cannot sign as someone else even by crafting the JSON.
  - Signature payload = user id + display name + timestamp + content SHA-256 + (where available) source IP.
- **Pilot gap:** the production identity source must be the agency's Entra ID / GCC tenant, not the dev-bypass user. In dev mode (`IS_DEV_BYPASS_AUTH_ENABLED=true`) anyone can sign as the bypass user — that env var must be **off** in any pilot deployment, and the deployment runbook must say so.
- **ESIGN/UETA note:** content hash + intent-to-sign + reproducible audit log satisfy ESIGN; nothing additional is required by §13663 itself.

### Req 4 — First-AI-draft retention

- **Status: ✅** (with one operational gap — see retention scheduler below)
- **Evidence in code:**
  - On `POST /reports/promote`, the originating assistant Message is marked `is_first_ai_draft=True` and `first_draft_locked_for_report_id=<report id>`. `routers/reports.py:96–151`.
  - The report stores both the message id and a verbatim text snapshot + SHA-256, so even if the Message document were somehow deleted, the report retains the canonical first draft.
  - `services/retention_sweeper.py` filters out any Message with `is_first_ai_draft=True` from purge — `routers/reports.py:` and `services/retention_sweeper.py:121–152` — and emits a `retention.first_draft_preserved` audit event recording the protected message + the report ids that locked it.
- **Operational gap:** the sweeper is a **callable service**, not a scheduled job. Nothing in `server.py` or `core/` invokes it on a cadence. **Pilot blocker:** wire it to a periodic task (APScheduler in-process, or external cron hitting an admin endpoint) before any agency goes live, otherwise retention will silently never run.
- **Non-statement labelling:** F4 audit export and the discovery package both label the first draft as *"First AI draft — not an officer statement (§13663(b))"* — required by the second sentence of (b).
- **Missing 403 test:** PRD §12 test case #2 ("attempt to mutate the first-draft Message → 403 + audit") is still ⏳. Enforcement today is by-omission (no edit endpoint exists), which is *probably* fine but a defense attorney would prefer an explicit deny path that audits attempts. Recommend: add a `PATCH /messages/{id}` that always 403s if `is_first_ai_draft=True` and writes a `FIRST_DRAFT_MUTATION_BLOCKED` audit event.

### Req 5 — Audit trail (person + media)

- **Status: ✅**
- **(c)(1) — person who used AI:**
  - Every `Message` has `user_id` (from `UserContext`).
  - Every `Report` has `signed_by` populated server-side (F19).
  - Every state change writes an `AuditEvent` with `actor_id` + `actor_display`.
  - F7 (chain-of-custody PDF) prints the complete prompt → response → promote → edit → sign chain with timestamps and actors.
- **(c)(2) — video / audio footage:**
  - `MediaInput` entity exists, is linked to the originating Conversation and to the Report.
  - Chain PDF includes a media inventory section listing every media item that was in context for any message in the chain.
- **Hash integrity:** each audit event chains via `prev_event_hash` (Merkle-style) so tampering is detectable. The chain PDF prints the running hash on the last page so a city attorney can verify it months later.

### Req 6 — Vendor restrictions

- **Status: 🟡 — software gate shipped (F10+F20), contract template not yet drafted**
- **Software side:**
  - `VendorAccessRequest` model captures purpose (one of: troubleshooting, bias-mitigation, accuracy, refinement, court-order, contracted-service) + scope (all / case-ids / report-ids) + time window.
  - `services/vendor_scope.py` enforces scope on every vendor-attributed request: off-scope → 403 + `VENDOR_ACCESS_SCOPE_VIOLATION` audit event (F20).
  - F17 (Refusal & Anomaly Report) surfaces every `vendor.access.used` event for routine review by the city auditor.
- **Contract side (not yet shipped):** the §13663(d) carve-outs ("court order, troubleshooting, bias mitigation, accuracy, refinement") are encoded in the *software* but must also appear in the agency's vendor contract. Recommend: a model contract clause in `docs/legal/vendor-data-handling-clause.md` aligned to the `VendorAccessPurpose` enum.
- **Vendor-admin surface (PRD §12 test case #6) is still ⏳:** today, vendor-side personnel hitting Cold Case at all is theoretical — there is no UI for them. When that surface is built, it must require an open `VendorAccessRequest` for every read, and bodies of prompts/responses must be access-logged per-view.

---

## 3. What is required vs what is "nice to have"

A pilot agency can go live with the **Required** items below. The **Recommended** items raise the audit-trail strength but are not statutorily required.

| Category | Item | Required by §13663 | Required by Cold Case design | Status |
|---|---|---|---|---|
| Policy | Agency policy doc adopted by city attorney | ✅ (a) chapeau | — | ❌ |
| Policy | Vendor data-handling contract clause | ✅ (d) | — | ❌ |
| Disclosure | Verbatim string on every page | ✅ (a)(1) | — | ✅ |
| Disclosure | AI program name + version on artifact | ✅ (a)(1) | — | ✅ |
| Signature | Officer e-signature gating export | ✅ (a)(2) | — | ✅ |
| Signature | Production IDP (not dev bypass) | implied by (a)(2) | ✅ | 🟡 |
| Retention | First-draft preservation in storage | ✅ (b) | — | ✅ |
| Retention | First-draft labelled "not an officer statement" | ✅ (b) sentence 2 | — | ✅ |
| Retention | Scheduled retention sweeper | implied by (b) | ✅ | ❌ (service exists, not scheduled) |
| Retention | Explicit 403+audit on first-draft mutation | — | ✅ (defensibility) | ❌ |
| Audit | Person attribution on every prompt/response | ✅ (c)(1) | — | ✅ |
| Audit | Media inventory on every chain | ✅ (c)(2) | — | ✅ |
| Audit | Tamper-evident audit event chain | — | ✅ (defensibility) | ✅ |
| Vendor | Scope enforcement (case/report ids) | implied by (d) | ✅ | ✅ |
| Vendor | Anomaly / vendor-access surface in audit UI | — | ✅ (defensibility) | ✅ (F17) |
| Vendor | Vendor-admin read surface with access-logging | implied by (d) when admin surface exists | ✅ | ❌ |

---

## 4. Pilot-readiness punch list (in priority order)

These are the items that must close before any California agency runs an AI-assisted official report through Cold Case in production.

1. **Draft `docs/legal/agency-policy-template.md`** — model policy for city-attorney adoption (Req 1). Should accompany the deployment as a deliverable, not an afterthought.
2. **Draft `docs/legal/vendor-data-handling-clause.md`** — model contract clause aligned to `VendorAccessPurpose` carve-outs (Req 6 contract side).
3. **Schedule the retention sweeper** — wire `services/retention_sweeper.py:sweep_once` to APScheduler or an external cron, with a daily run and a `retention.sweep_completed` audit event recording counts. Add a manual-trigger admin endpoint behind `admin.retention.run`.
4. **Add explicit first-draft mutation deny path** — `PATCH /messages/{id}` returning 403 + `FIRST_DRAFT_MUTATION_BLOCKED` audit when `is_first_ai_draft=True`. Closes PRD §12 test case #2.
5. **Pilot-deployment runbook** — must mandate `IS_DEV_BYPASS_AUTH_ENABLED=false`, agency IDP wired, model-name pin verified, agency letterhead env vars populated, retention scheduler running. Recommend a `/admin/compliance/preflight` endpoint that asserts all of these and refuses to report "ready" otherwise.
6. **Vendor-admin surface — "no surface" attestation (resolved 2026-05-20).** Pilot deployments of Cold Case **do not expose any vendor-admin UI or vendor-attributed read API**. Cold Case engineering is not "the vendor" in the §13663(d) sense — the vendor of record is the agency's LLM provider (OpenAI / GCC Copilot tenant / future provider), and that vendor's data exposure is governed by the agency contract clause at [`vendor-data-handling-clause.md`](./vendor-data-handling-clause.md) plus the `VendorAccessRequest` workflow if/when Cold Case engineering needs case-scoped support access. **Constraint for future work:** if and when a vendor-admin read surface is added (e.g., a "support backstage" view for Cold Case engineering or a future bias-audit dashboard for the LLM provider), it must (a) require an open `VendorAccessRequest` for every read, (b) log every prompt/response body view as a `vendor.access.used` audit event, and (c) be added to the pilot-deployment runbook's "must be disabled in production unless approved" list. PRD §12 test case #6 stays ⏳ until that surface exists, at which point it becomes a release blocker for that surface.
7. **`OPENAI_MODEL` sanity check in `.env`** — current value `gpt-5.5` is not a valid OpenAI model id, so any real Copilot call will fail. Pilot deployments must pin a real model id and the runbook must reject deploys with unrecognized ids.

---

## 5. Things that look like compliance gaps but aren't

- **"Cold Case doesn't store the case documents"** — by design. Documents stay in the agency's Azure/S3 / evidence.com; Cold Case stores pointer + hash. §13663 places no obligation on *where* the source documents live, only on the audit trail for the AI use. The current architecture is **stronger** than a naïve "store everything in Cold Case" approach because it keeps source-of-record in the customer's existing CJIS-aligned storage.
- **"Cold Case doesn't run its own model"** — by design. (e)'s AI definition covers the Copilot endpoint the agency already uses; Cold Case is a governance wrapper. Building a Cold-Case-hosted model would expand the (d) vendor surface, not reduce it.
- **"Discarded re-asks aren't deleted"** — by design. (c) audit-trail requirement is best served by preserving every prompt, including discarded ones, so a defense attorney cannot allege exculpatory drafts were destroyed. F4 audit export includes them with explicit "discarded" / non-promoted labelling.
- **"Cold Case doesn't drive §1054.1 discovery timing"** — out of scope for this statute. F8 produces the discovery artifact when the DA's office requests it; the cadence is the DA's workflow, not §13663's.

---

## 6. Annual / ongoing obligations after pilot

These are obligations that **renew** rather than ship-once.

- **Re-verify SB-524 hasn't been amended** before each Cold Case release. Capture the leginfo URL retrieval date in `sb524-text.md` and re-pull annually (calendar item for City Attorney + Cold Case engineering).
- **AI Program Inventory (F16)** — produce annually for the agency's SB-524 attestation. The inventory pulls from real production usage, not configured aliases.
- **Anomaly Report (F17)** review cadence — recommend monthly review by city auditor; refusal events and vendor-access events both surface here.
- **Retention sweeper drift check** — quarterly: pick 5 random closed cases, verify each retained first-draft is still readable and the SHA-256 matches the report's snapshot hash.
- **Vendor contract re-attestation** — any time the agency adds or replaces an AI vendor, the §13663(d) clause must apply and a `VendorAccessRequest` workflow must exist.

---

## 7. Open questions for City Attorney

These are items where Cold Case's engineering position is "we picked one, but you should confirm."

1. **Definition of "first draft" when multiple regen attempts precede a promote.** Cold Case treats the assistant Message that gets promoted as the first draft. Alternative reading: every regen is a "first draft" and all must be retained as drafts. Our reading aligns with (e)'s "*the initial document or narrative produced solely by AI*" applied to *the report*, not *every Copilot turn*. **City Attorney sign-off requested.**
2. **Retention floor for a Report whose Case is later expunged.** §13663(b) says "as long as the official report is retained." If a Case is sealed, do the AI artifacts also seal, or are they retained on a separate clock? Cold Case currently slaves AI-artifact retention to the report; sealing the report seals the chain. **Confirm this aligns with agency policy.**
3. **PRA / discovery production format.** F8 Discovery Package emits a self-signing ZIP. Confirm the city's preferred format (PDF bundle? evidence.com upload?) before pilot.
4. **Vendor "troubleshooting" purpose granularity.** §13663(d) permits "troubleshooting" without further definition. Cold Case requires a free-text justification on the `VendorAccessRequest`. Confirm whether the city wants a closed list of acceptable troubleshooting reasons (e.g. "incident response — ticket #") or accepts free-text + audit review.

---

## 8. Document maintenance

- **Update trigger:** any PR that touches `routers/`, `services/report_export.py`, `services/retention_sweeper.py`, `models/report.py`, or `models/audit_event.py` must consider whether this status doc needs an update, and the PR template should ask.
- **Source-of-truth ordering** if these documents disagree: (1) the statute itself, (2) `sb524-text.md`, (3) this status doc, (4) PRD §12 matrix. Engineering details (PRD) follow the legal framing (this doc), not the other way around.
