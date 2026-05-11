# Cold Case — Comprehensive PRD

**Version:** 0.4.0 (MVP backend implemented + §13663 smoke tests green)
**Status:** backend MVP landed locally — frontend + real Copilot wiring next
**Date:** 2026-05-11
**Sources:**
- `docs/usecase-transcript.txt` — interview with Detective Gaudi (cold case investigator) + IT sponsor, 2026-05-11
- California **Senate Bill 524** (2025–2026 reg. session), enacting **Penal Code §13663**, signed by Governor Newsom 2025-10-10, **effective 2026-01-01** — full mapping in §12 below.

---

## 1. Executive summary

Cold Case is a **governance & audit layer** that wraps a law-enforcement agency's existing Microsoft 365 GCC Copilot (or equivalent in-tenant LLM) so detectives can use AI to summarize police reports, build timelines, draft interview questions, and look up penal codes / CalCrim — while producing the **prompt-and-output audit trail** required by California **SB-524** (AI-in-government accountability).

The detective never leaves the agency's "four walls": source documents stay in the agency's Azure/S3, analysis runs in the agency's GCC Copilot tenant, and Cold Case stores only **metadata + lineage** (prompts, outputs, approver, version, hash). Every AI-generated artifact is stamped "*generated with AI Copilot by &lt;user&gt;*" and the full prompt chain (including discarded drafts) is recoverable for legal review.

**Value:** detective today PDFs each Copilot answer by hand and uploads to evidence.com. Cold Case automates that, adds the legally-required chain-of-custody for prompts, and unblocks AI use across the agency without legal/compliance friction.

## 2. Problem statement

### 2.1 Current state (Detective Gaudi's workflow today)

1. Patrol completes a report; detective receives it as a PDF.
2. Detective opens **Copilot (GCC tenant)** and creates a Copilot **notebook** per case.
3. Detective uploads the patrol PDF (and any reports they have written) into the notebook.
4. Detective prompts Copilot to:
   - Summarize the police report.
   - Build a timeline of events for the DA.
   - Review the detective's own report for gaps.
   - Suggest follow-up interview questions.
   - Look up Penal Code / CalCrim references and check the report against them.
5. When an output is useful, the detective **manually exports a PDF** of the Copilot conversation and uploads it to **evidence.com** as the artifact of record.
6. There is **no automatic record** of which prompts produced which output, or which drafts were discarded.

### 2.2 Pain points

| Pain point | Frequency | Impact |
|---|---|---|
| Manual PDF export of every Copilot interaction the detective wants to keep | Multiple times per case | Time sink; easy to forget; not a tamper-evident record |
| No prompt-level audit trail (SB-524 requires the prompts + interactions that led to the published output) | Every AI use | Legal/compliance risk; could disqualify AI-assisted work |
| Discarded drafts (re-ask the same question 2–3 times) are not preserved | Every AI use | Defense can argue undisclosed exculpatory drafts |
| AI-generated text not visibly marked as AI-generated when it lands in evidence | Every export | Could be mistaken for human-authored work product |
| No agency-wide visibility for city / city attorney to audit AI use | Continuous | City has no way to comply with SB-524 audit requests |
| Long-retention cases (homicide = effectively forever) — Copilot notebook lifecycle doesn't match | Cold case workload | Risk of losing chain-of-custody when Copilot notebooks are pruned |

### 2.3 Not-goals (MVP)

Explicitly **out of scope** to keep MVP focused (per Dan's stated scope discipline in the call):

- ❌ Replacing Copilot or running our own LLM analysis (the value is in governance, not the model).
- ❌ Cross-document graph / "who knows whom" link analysis. (Stretch goal — detective did not confirm it as a need; we noted "interesting question" but the SB-524 audit trail is *the* need.)
- ❌ Audio / video transcription. Detective confirmed Copilot doesn't accept audio/video today; not a current pain.
- ❌ Storing case documents in Cold Case's database. Documents live in the agency's Azure/S3; we store metadata + references only.
- ❌ Replacing evidence.com. Cold Case can export to evidence.com, not supersede it.

## 3. User personas

### 3.1 Primary user — **Detective / cold case investigator** ("Detective Gaudi")
- Works individual cases (homicides, long-retention).
- Comfortable with Copilot, not a power user. Wants the friction *removed*, not a new toolchain.
- Trusts the agency's GCC tenant; will not paste case data into external chatbots.
- Needs to defend their work product to the DA and (potentially) defense counsel.

### 3.2 Secondary user — **Records / supervising sergeant**
- Reviews and approves AI-generated artifacts before they become part of the case file.
- Needs to see which version of an AI output was approved and by whom.

### 3.3 Compliance / audit user — **City attorney / city auditor**
- Periodically (or on subpoena) needs to produce the **full prompt history** for any AI-generated work product.
- Determines what's released externally; Cold Case just needs to make the data retrievable. ("The city and their lawyers determine at that time.")

### 3.4 Executive sponsor — **Agency IT / CIO** (the IT sponsor on the call)
- Standardized the agency on GCC Copilot specifically because it's CJIS-aligned.
- Needs auditability + a governance story that satisfies SB-524 statewide ("any other California agency is gonna keep that up").

## 4. Solution overview

### 4.1 Core capabilities (MVP)

1. **Case workspace** — a Cold Case "case" is a folder of source documents (PDFs of patrol reports, detective reports, scans). Documents are stored in the agency's Azure/S3; Cold Case stores the pointer + hash.
2. **Chat-with-case UI** — chat interface inside Cold Case that proxies prompts to the agency's GCC Copilot, scoped to the case's documents.
3. **Prompt + output lineage** — every prompt, every response (including discarded drafts), the user who issued it, the timestamp, the model, and the source documents in context are persisted as immutable audit records.
4. **Approve / publish** — detective marks a specific AI output as the version they're using. Approved outputs are stamped *"generated with AI Copilot by &lt;user&gt; on &lt;date&gt;"* and exported as PDF (drop-in replacement for today's manual PDF-to-evidence.com flow).
5. **Audit export** — city attorney / auditor can pull the full prompt-and-output chain for any approved artifact, or for any user / case / date range.
6. **Configurable retention** — default 2 years for metadata; homicide / cold cases extendable to 7+ years or indefinite. Documents themselves live in the customer's storage, lifecycle controlled by the customer.

### 4.2 Phase roadmap

| Phase | Scope | Value |
|---|---|---|
| **MVP** | Case workspace · chat proxy to GCC Copilot · prompt/output lineage · approve+export · SB-524 audit report | Replaces the manual PDF workflow; produces the audit trail the law requires |
| **Phase 2** | Templated workflows (summarize, build DA timeline, gap-check against CalCrim, interview-question generator) as one-click actions; PDF generation with agency letterhead | Reduces detective time-per-case; standardizes outputs across detectives |
| **Phase 3 (stretch)** | Cross-document timeline + relationship graph ("how is Dan related to everything in this case") · audio/video ingestion when Copilot supports it | The "interesting" stretch the detective wasn't ready to commit to — revisit once MVP is in production |

## 5. MVP features

### F1 — Case workspace
- **What:** detective creates a case, adds (references to) PDFs stored in the agency's Azure/S3.
- **Data:** `Case { id, case_number, title, classification (homicide / robbery / …), retention_policy, created_by, created_at, status }`. `Document { id, case_id, storage_uri, sha256, original_filename, uploaded_by, uploaded_at, mime_type, page_count }`.
- **API:** `POST /cases`, `GET /cases`, `POST /cases/{id}/documents` (registers a pointer; doesn't upload the file).
- **UI:** list view (cases) → detail view (documents + chat panel). Like the redaction-tool layout Dan showed on the call.
- **Acceptance:** detective can create a case, register 3 PDFs by URI, and see them listed. Hash is computed on registration.
- **Out of scope:** uploading binary PDFs into Cold Case storage; OCR; thumbnails.

### F2 — Chat with case (GCC Copilot proxy)
- **What:** chat interface within the case detail view. Each message proxies through to the agency's GCC Copilot, scoped to the case's documents.
- **Data:** `Conversation { id, case_id, user_id, started_at }`. `Message { id, conversation_id, role (user/assistant/system), content, parent_message_id, prompt_tokens, completion_tokens, model, timestamp, in_context_document_ids[] }`.
- **API:** `POST /cases/{id}/conversations`, `POST /conversations/{id}/messages` (returns assistant message including model + context).
- **UI:** standard chat UI; sidebar lists the case's documents; clicking a document opens it.
- **Acceptance:** detective asks "summarize the patrol report" and gets a response; the prompt + response + which documents were in context are persisted; retries against the same question create new Messages with the same `parent_message_id`.
- **Out of scope:** streaming UI (nice-to-have); model selection (use the agency's default GCC Copilot endpoint).

### F3a — Revision history of the draft

- **What:** every edit to the report draft (`PATCH /reports/{id}`) appends a `ReportRevision` to an append-only list on the Report. Each revision captures `{seq, text, editor_id, editor_display, timestamp, content_sha256, byte_count}`. The first revision is the AI's first draft (verbatim); subsequent revisions are officer edits. The revision whose hash equals `signature.content_sha256` is the one that was signed.
- **Why:** §13663(c) audit-trail strength benefits from a complete edit history. Combined with the §13663(b) first-AI-draft snapshot, this gives the city attorney an unambiguous timeline: "AI wrote X, officer changed it to Y over N revisions, officer signed revision K."
- **UI:** report drawer surfaces a collapsible "Revision history (N)" panel listing every revision with timestamp + editor + hash prefix. The signed revision is flagged. Clicking a revision shows a side-by-side diff against the first AI draft.

### F3b — Live source verification in the editor

- **What:** the report editor renders a **live citation preview** beneath the editable textarea. Every `[src: <filename>, L<n>]` token in the draft becomes a clickable chip that opens the cited document and highlights the cited line — same behavior as in chat. This lets the officer verify each citation *before* signing rather than only after.
- **Why:** §13663(a)(2) attestation requires the officer to certify that the facts in the report "are true and correct." Click-through verification while editing makes the certification mechanical: the officer reads the claim, clicks the chip, sees the source line, and only then keeps it in the draft.

### F3 — Approve, sign & publish (the "official report" path)
- **What:** detective selects one assistant Message as the basis for an **official report**, optionally edits it, applies their **electronic signature**, and exports. Cold Case freezes the **first AI draft** (the unedited AI output that started the chain) separately and immutably, per §13663(b).
- **Data:** `Approval { id, first_draft_message_id, final_text, ai_programs_used[] (name+version), approved_by, approved_at, signature (e-sig payload), exported_artifact_uri, export_target }`. The `first_draft_message_id` MUST reference the **initial AI-only output** in the conversation, not the edited final.
- **API:** `POST /messages/{id}/promote-to-report` (creates the report draft with the chosen Message as `first_draft`); `POST /reports/{id}/sign` (applies e-signature, freezes, exports).
- **UI:** "Use as official report" button → editor opens with the AI text + a visible "First AI draft (immutable, retained per §13663(b))" panel showing the original AI text → "Sign & export" button.
- **Acceptance:**
  - Exported PDF includes on **every page** the statutory disclosure: *"This report was written either fully or in part using artificial intelligence."* plus identification of the AI programs used (model name + version).
  - The officer's signature (electronic) is present and verifies they reviewed contents and that facts are true and correct.
  - The first AI draft is retrievable for as long as the official report is retained.
- **Out of scope:** non-Copilot LLMs (Phase 2).

### F4 — SB-524 audit report
- **What:** the city attorney / auditor can pull, for any approved artifact, the full prompt chain that led to it (including discarded drafts and re-asks).
- **Data:** derived from F2 + F3 — no new entities.
- **API:** `GET /audit/artifact/{approval_id}` → full conversation tree. `GET /audit/user/{user_id}?from=&to=` → all approvals + chains.
- **UI:** auditor view (gated by the `audit.read` permission). Linear, printable rendering of the full chain.
- **Acceptance:** for any approved artifact, the report shows every prompt (including discarded re-asks), every response, who, when, model, and which documents were in context.

### F6 — Source-cited output + click-through verification

- **What:** every factual claim in an assistant response, in a promoted report draft, or in a signed report carries a citation token pointing to the exact document and line that supports it: `[src: <filename>, L<n>]`. The token renders as a clickable chip in the UI; clicking it opens the cited document and highlights the cited line so the officer can verify accuracy before signing.
- **Why this matters:**
  - **Officer attestation (§13663(a)(2))** requires the officer to verify *"that the facts contained in the official report are true and correct."* Click-through citations make that verification mechanical instead of subjective.
  - **Audit trail (§13663(c))** is strengthened: when the city attorney pulls the chain, every claim in the final report points back to a specific span in a source document.
  - **Hallucination guard:** an LLM that *must* emit `[src: ...]` tokens is far less likely to invent facts; an officer who *sees* a fact with no citation will treat it as inferred.
- **Mechanism:**
  - When documents are injected into the LLM's system prompt, each line is prefixed with its line number (`[L17] At 06:18 hrs on 04/12/1992 dispatch received…`).
  - The system prompt instructs the model to cite every factual claim using the token format above.
  - The text-extraction endpoint (`GET /cases/{id}/documents/{doc_id}/text`) returns both the raw text and a `numbered` form so the UI renders the *exact* same line numbers the model saw.
  - The frontend parses `[src: <filename>, L<n>]` tokens out of any rendered LLM text (message bubble, report draft, even the signed report's final text) and replaces them with chips. Click → switches the document viewer to that file, scrolls to the line, flashes it for 1.5s.
- **Acceptance:**
  - A "build a timeline" prompt against the seeded Riverside Park case returns timeline entries that each end with a `[src: ..., L<n>]` chip.
  - Clicking the chip opens the correct document and highlights the line that contains the cited event.
  - The chip set persists into the report editor, the audit-chain view, and the exported PDF (where it renders as plain text since PDFs aren't interactive).

### F5 — Retention
- **Statutory rule (§13663(b)):** the **first AI draft** of any **official report** must be retained **for as long as the official report is retained**. There is no shorter floor permitted by Cold Case.
- **Data:** `Case.retention_policy` ∈ { `match_official_report` (default), `7y`, `indefinite` }. For any Conversation that produced an Approval, the first-draft retention always follows the report's retention even if the case is closed.
- **Rule:** Cold Case retains lineage **metadata** (incl. first drafts) per the statute. Source documents live in the agency's storage; their lifecycle is the agency's responsibility, but Cold Case will refuse to purge metadata for a Conversation that produced a still-retained official report.
- **Acceptance:** for any approved report, the first AI draft + the full Conversation tree remain retrievable until the agency explicitly attests the underlying report is no longer retained.

## 6. Data model (MVP)

Entities:
- **`Case`** — investigative case folder.
- **`Document`** — pointer to a PDF / text artifact in the agency's storage (URI + sha256).
- **`MediaInput`** — pointer to bodycam / audio / video evidence used as AI input. Required by §13663(c)(2) even if MVP Copilot can't ingest it directly; schema-ready for when it can.
- **`Conversation`** — chat session against a case.
- **`Message`** — single prompt or response. The first assistant Message in a chain that produced an official report is flagged `is_first_ai_draft=true` and becomes **immutable** at Report sign time.
- **`Report`** — the **official report** under §13663. Contains the final signed text, the link to the `first_ai_draft` Message, the AI programs used (name+version), the officer e-signature, the disclosure stamp (literal statutory text), and the export target URI. Once signed, all fields are immutable.
- **`Approval`** — supersedes prior approvals on the same Report (revision history). Most reports have one.
- **`AuditEvent`** — append-only log of: case created, document/media registered, conversation started, message sent/received, report drafted/signed/exported, retention changed, vendor-access event.

Indexes:
- `Case` — `(case_number)` unique per tenant; `(status, created_at)`.
- `Document` — `(case_id)`, `(sha256)`.
- `MediaInput` — `(case_id)`, `(sha256)`, `(source_type)`.
- `Message` — `(conversation_id, timestamp)`, `(parent_message_id)`, `(is_first_ai_draft)`.
- `Report` — `(case_id)`, `(first_ai_draft_message_id)` unique, `(signed_at)`.
- `Approval` — `(report_id, approved_at)`.
- `AuditEvent` — `(case_id, timestamp)`, `(user_id, timestamp)`, `(event_type, timestamp)`.

All entities partition by `app_id="coldcase"` (Launchpad Admin Pattern) and by `tenant_id` per agency.

## 7. Business rules

1. **No detective bypass.** All Copilot traffic from Cold Case is logged. Direct Copilot use outside Cold Case is the failure mode this app exists to replace.
2. **Messages are immutable.** Once persisted, a Message cannot be edited or deleted — only superseded by a newer Message in the same chain.
3. **First AI draft is frozen at promote-time.** When a detective promotes a Message to a Report (§13663 "official report"), the chosen assistant Message is flagged `is_first_ai_draft=true` and locked. The detective may edit the **report text** all they want, but the first-draft Message cannot change.
4. **Statutory disclosure is exact.** Every page of an exported official report carries verbatim:
   - *"This report was written either fully or in part using artificial intelligence."*
   - Identification of the AI program(s) used (model name + version).
   No paraphrase, no abbreviation. The wording is hardcoded; only the program identification is dynamic.
5. **Officer signature is required to export.** A Report cannot be exported until the officer applies their electronic signature attesting they reviewed the contents and that the facts are true and correct (§13663(a)(2)). Signature payload includes user id, timestamp, IP, and a hash of the final text.
6. **Drafts are not officer statements.** Per §13663(b), drafts (including the first AI draft) do **not** constitute the officer's statement and are flagged as such in any audit export so they cannot be misrepresented as testimony.
7. **Media inputs are tracked.** If any video / audio / bodycam media was used as input to the AI (directly or transcribed first), the `MediaInput` records are linked to the Conversation and to the Report (§13663(c)(2)).
8. **Customer data stays customer-side.** Source documents and media are never copied into Cold Case storage. We store URIs + hashes + lineage.
9. **Vendor-use restriction (§13663(d)).** Cold Case (Darwin) does not share, sell, or otherwise use agency-provided data except (a) to provide service to that agency, (b) to comply with a court order, or (c) for troubleshooting / bias-mitigation / accuracy improvement / system refinement. Any access under (c) is itself logged as an `AuditEvent` of type `vendor_access`, with the responsible Darwin operator's identity.
10. **First-draft retention floor.** The first AI draft of any signed Report is retained for as long as the Report is retained (§13663(b)). Cold Case refuses to purge first-draft Messages while the parent Report's retention is still active.
11. **AI programs identified per Report.** The exact model name + version used to produce each Report is captured at sign time. If a Conversation used multiple models, all are listed.
12. **Citations are mandatory in AI output.** Every factual claim in an assistant message must carry a `[src: <filename>, L<n>]` citation. The officer is expected to click each citation before signing. Unsourced claims should be challenged or removed.
13. **Revisions are append-only.** Every `PATCH /reports/{id}` appends a `ReportRevision` with timestamp, editor identity, and content hash. Revisions are never deleted or edited in place. The signed revision is the one whose hash matches `signature.content_sha256`.
14. **Signed PDF is the canonical artifact.** Once a report is signed and exported, the resulting PDF is the legal artifact. It is retrievable via `GET /reports/{id}/pdf` as long as the Report retention policy holds. Re-exports overwrite a `superseded` flag on prior PDFs; the original is never deleted while the report is retained (§13663(b) extends to the exported PDF in addition to the first AI draft).
15. **Implicit document context defaults to "all case docs."** When `POST /conversations/{id}/messages` receives an empty `in_context_document_ids`, the server resolves it to *every document on the case* and records `implicit_document_context=true` on the persisted Message and the `MESSAGE_USER` audit event. Rationale: a detective asking about *this* case expects the AI to know about the case's documents without manual toggling, and "I do not have access to the documents" is the worst possible failure mode for a citation-driven workflow. Media stays explicit (body cam / interview audio is heavy and rarely desired by default).
16. **OCR fallback for image-only PDFs.** `services/document_text.extract_text` tries `pypdf` first; if the embedded text layer averages fewer than `COLDCASE_OCR_MIN_CHARS_PER_PAGE` non-whitespace characters per page (default 40), it falls back to OCR via `pymupdf` (render at `COLDCASE_OCR_DPI`, default 200) + `pytesseract.image_to_string` (`COLDCASE_OCR_LANG`, default "eng"). Results are memoized at the cache layer so OCR runs at most once per immutable document version. Requires the `tesseract` binary in the backend image (`apt-get install tesseract-ocr`). Pattern mirrors the sibling `ada` project's WCAG remediation pipeline.

## 8. Provider architecture

Cold Case's provider seam (from the starter kit's six providers) maps as:

| Provider | Mock (dev) | Real (production) |
|---|---|---|
| **Employee** (user lookup) | Seed users (detective, sergeant, auditor) | Agency Entra ID / AD |
| **Email** | Logs to DB | Microsoft Graph (notify approver on approval) |
| **Calendar** | Synthetic | Not used MVP |
| **Training** | Not used MVP | Not used MVP |
| **Evaluation** | Not used MVP | Not used MVP |
| **Photos** | Not used MVP | Not used MVP |
| **LLM** (new) | Echo / local Ollama (`qwen3.6:35b-a3b-nvfp4`) | Agency GCC Copilot endpoint |
| **Document storage** (new) | Local `./uploads` | Agency Azure Blob / S3 |
| **Case-file export** (new) | Drop to filesystem | evidence.com API |

The two **new** provider seams (`LLM`, `Document storage`, `Case-file export`) need to be added to `server-py/providers/`. The four unused starter-kit providers can be left in place (cheap) or pruned in a later commit.

## 9. Screens + navigation

- `/` — case list (filterable by status + classification).
- `/cases/new` — create case.
- `/cases/:id` — case detail. Three-pane: documents (left), document viewer (center), chat (right). Mirrors the redaction-tool layout shown on the call.
- `/cases/:id/audit` — full audit timeline for this case (gated by `audit.read`).
- `/audit` — agency-wide audit search (gated by `audit.read`).
- `/admin` — Launchpad Admin Pattern (RBAC, roles, mappings).

## 10. Prototype limitations

- Single-tenant (agency) deployment per instance for MVP. Multi-tenant is later.
- Copilot proxy uses a single configured endpoint; per-user delegated tokens come in Phase 2.
- evidence.com export uses a mock that writes a PDF to disk; real evidence.com integration is a Phase-2 ticket.
- No mobile UI; field detectives use a laptop today and that's fine.

## 11. Open questions (raised in the call, not yet answered)

1. **Are documents already in Copilot notebooks?** Detective confirmed yes — "I have been creating the notebooks." Decide whether Cold Case **creates** the notebook on the agency's behalf or **adopts** existing notebooks via a sync.
2. **Token delegation.** Per-user OAuth to GCC Copilot vs service principal? Per-user is stronger for §13663(c)(1) "person who used AI" attestation.
3. **evidence.com integration mode.** API push, mailbox drop, or detective-driven download-then-upload?
4. **Letterhead.** Agency-supplied PDF template + signature block style.
5. **E-signature standard.** ESIGN / UETA-compliant signature, or a simple hashed-attestation? §13663(a)(2) accepts physical or electronic.
6. **Penal-code-required officer policy.** §13663(a) (chapeau) requires the *agency* to "maintain a policy." Cold Case can ship a policy template — confirm scope with city attorney.
7. **Disclosure-page mechanics.** Header vs footer vs full-page cover? Statute says "include" not where; recommend footer-on-every-page + cover sheet for unambiguous compliance.

## 12. SB-524 / Penal Code §13663 — compliance matrix

Each row maps a statutory subdivision to the Cold Case feature/rule that satisfies it. **This matrix is the acceptance gate for MVP.**

| §13663 subdivision | Requirement (paraphrase, exact text in `docs/legal/sb524-text.md` once captured) | Cold Case implementation | PRD ref |
|---|---|---|---|
| **(a)(1)** | Report must identify AI program(s) used and bear exact text *"This report was written either fully or in part using artificial intelligence."* | F3 + Business rule #4: disclosure footer on every exported page, hardcoded statutory text + dynamic `ai_programs_used[]` list | §5/F3, §7/#4 |
| **(a)(2)** | Officer's signature (physical or electronic) verifying review + that facts are true and correct | F3 `POST /reports/{id}/sign` — required to export. Signature payload = user id + timestamp + content hash + IP | §5/F3, §7/#5 |
| **(a) chapeau** | Agency must "maintain a policy" requiring (a)(1)+(a)(2) on every AI-assisted official report | Ship a policy template under `docs/legal/agency-policy-template.md`; admin attests at tenant setup | open Q #6 |
| **(b)** | First AI draft retained as long as the official report is retained; drafts are NOT officer statements | F5 + Business rules #3, #6, #10. `Message.is_first_ai_draft=true`, immutable post-promote, retention slaved to `Report.retention`. Audit exports label drafts as non-statements | §5/F5, §6, §7/#3,#6,#10 |
| **(c)(1)** | Audit trail identifies the person who used AI | Every Message has `user_id`; every Report has `signed_by`; AuditEvent stream is per-user. F4 surfaces this | §5/F4, §6 |
| **(c)(2)** | Audit trail identifies video/audio footage used as input | `MediaInput` entity, linked to Conversation + Report | §6, §7/#7 |
| **(d)** | Vendor cannot share/sell/otherwise use agency data except for agency, court order, or troubleshooting/bias/accuracy/refinement | Business rule #9 + contractual MSA term + `AuditEvent.vendor_access` for any (c)-purpose access | §7/#9 |
| **(e) — "AI" definition** | Systems that "infer from the input it receives how to generate outputs" — covers narrative-drafting + generative report enhancement | All Copilot interactions are in scope. Documented in `services/llm_provider.py` | §8 |
| **(e) — "official report" definition** | The **final version** signed by the officer | `Report` entity is "official report"; pre-sign drafts are not | §6, §7/#5 |
| **(e) — "first draft" definition** | The initial document or narrative produced **solely by AI** | `Message.is_first_ai_draft` set only on the assistant Message before any officer edit | §6, §7/#3 |

### Statute-driven test cases (must pass before any agency goes live)

Status legend: ✅ = automated smoke test passes locally; ⏳ = not yet covered.

1. ✅ Export a Report; open the PDF; **every page** contains the verbatim disclosure string + at least one AI program name. (Smoke test #12–#13 — `pypdf` extraction confirms text on both rendered pages.)
2. ⏳ Attempt to mutate the `first_ai_draft_message_id` Message → API returns 403 and writes an `AuditEvent`. (No edit endpoint exists; enforcement is by-omission today. Phase 2: add an explicit endpoint that always 403s + audits.)
3. ✅ Attempt to export a Report without signing → API returns 422 referencing §13663(a)(2). (Smoke test #9.)
4. ⏳ Mark a Case closed with retention `match_official_report`; attempt to purge any Message that is a first AI draft → purge skipped, AuditEvent emitted. (Purge job not yet implemented.)
5. ✅ Audit export for a Report renders the full Conversation tree with first draft labeled "First AI draft — not an officer statement (§13663(b))". (Smoke test #14.)
6. ⏳ Vendor-side admin attempts to view a prompt body → blocked unless logged under `vendor_access` with operator id + reason. (Vendor-side admin surface not yet built.)
7. ✅ AI program identification in the export matches the `model` field recorded on the `first_ai_draft` Message. (Smoke test #7, #15.)
8. ✅ Same Message cannot be promoted twice → 409. (Smoke test #8.)
9. ✅ Homicide classification on case-create auto-suggests indefinite retention. (Smoke test #2.)

## 13. Out-of-scope but worth flagging to the agency

These come up adjacent to §13663 and the agency should know Cold Case does **not** address them in MVP:
- **General records-retention rules** beyond §13663 (e.g., GC §34090, evidence-code retention).
- **CJIS-policy compliance** of the GCC Copilot endpoint — that's the agency's M365 GCC posture, not Cold Case's.
- **Public Records Act / Brady disclosure tooling** — Cold Case stores the data PRA / Brady requests would draw from, but does not implement the request workflow.
- **Disclosure to defendants** in prosecution — Cold Case provides the exportable audit, but the DA / defense process is outside.

## Changelog

| Version | Date | Changes |
|---|---|---|
| 0.4.0 | 2026-05-11 | Backend MVP landed: domain models, LLM + DocumentStorage provider seams, F1/F2/F3/F4 routers, §13663-compliant PDF export. End-to-end smoke (17 steps incl. 9 statute-driven checks) green |
| 0.3.0 | 2026-05-11 | SB-524 / Penal Code §13663 statutory mapping; added Report entity + MediaInput; rewrote business rules and F3 around first-AI-draft + statutory disclosure text; added §12 compliance matrix |
| 0.2.0 | 2026-05-11 | Requirements extracted from use-case interview (`docs/usecase-transcript.txt`) |
| 0.1.0 | 2026-05-11 | Initial scaffold from launchpad-starter-kit |
