# Cold Case — Comprehensive PRD

**Version:** 0.8.0 (Phase A workspace + Phase B tags/people/timeline/notes + Phase C AI extraction + hash-chained audit integrity + AI provenance + cross-case graph)
**Status:** Pilot-ready surface area complete. Open: evidence.com integration + real GCC Copilot provider + agency Entra wiring.
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

### F7 — Chain-of-Custody PDF (per signed report)

- **What:** a printable PDF rendering of `GET /audit/reports/{id}/chain` that travels alongside the signed-report PDF. Contains, in order:
  1. **Cover page** mirroring the signed-report identifiers (Report ID, Case #, signed-content_sha256, AI program(s) used + version, signer + badge + signed_at) and a **tamper-detection hash** (see *Audit-integrity hash* below) printed in the footer.
  2. **Case header** + the case-level §13663 disclosure.
  3. **Source-document inventory** — every Document in context with `(filename, sha256, mime, size, registered_at)`. Pointer-only; no body content.
  4. **MediaInput inventory** — every `MediaInput` registered to the case with `(source_type, sha256, duration_seconds, captured_at, description)`. Required by §13663(c)(2) — auditor must see what video/audio was input to the AI.
  5. **Conversation chain** — every user prompt and assistant response in chronological order **including discarded re-asks**. Citation tokens render verbatim (static text). Assistant messages with `extra.refusal_detected=true` are flagged with a red `⚠ REFUSAL DETECTED` marker; the audit reader sees the LLM hedged despite docs being supplied.
  6. **§13663(b) first AI draft** — verbatim, labeled "Not an officer statement (Penal Code §13663(b))."
  7. **Revision history** — every revision with its hash + editor + timestamp + note + delta-in-bytes vs the prior revision. The signed revision is flagged.
  8. **AuditEvent timeline** — every event keyed to this report.
  9. **Citation coverage stats** — count of factual paragraphs in the signed text vs count carrying a `[src: ...]` citation. Anything below 100% surfaces as a footer line for the auditor to flag.
  10. **"How to verify"** appendix — names the statutory hooks (§13663(a)(1), (a)(2), (b), (c)(1), (c)(2)), the relative `/audit/reports/{id}/chain` URL, and instructions for re-running the audit-integrity hash.
- **Why:** today, the chain of custody underlying a signed report is reachable only via a JSON API. When defense counsel or the city attorney subpoenas the prompt history that produced an AI-assisted official report, the agency cannot hand them JSON — they need a paginated, hash-pinned PDF. §13663(c) requires the agency to "maintain an audit trail"; this is the printable form of that trail.
- **Mechanism:**
  - New module `services/chain_export.py` (sibling to `report_export.py`) that consumes the existing `/audit/reports/{id}/chain` payload and renders via ReportLab.
  - New endpoint `GET /reports/{id}/chain.pdf` — streams the file. Cached on disk at `uploads/reports/<report_id>.chain.pdf`. (Audit artifact, deliberate carve-out from rule #17 — see clarified rule below.)
  - **Auto-pair on export.** When the user signs and exports a report (`POST /reports/{id}/export`), Cold Case generates **both** PDFs in the same operation: `<report_id>.pdf` and `<report_id>.chain.pdf`. Both linked from `Report` (new `chain_artifact_uri` field). When evidence.com push lands (Phase 2) both go together.
  - **Audit-integrity hash.** Each chain PDF embeds in its footer `chain_sha256 = sha256(report_id || first_ai_draft_hash || signed_content_hash || generated_at || conversation_id || all_revision_hashes_concatenated)`. The same hash is reproducible by hitting `GET /audit/reports/{id}/chain` and recomputing — an auditor with just the PDF can verify integrity without trusting our retention.
  - Self-identification: chain PDF carries Report ID + Case # + signed-content-hash in the same footer stripe + metadata Keywords as the signed report. Metadata Subject reads "Cold Case Report — chain of custody (§13663(c) audit trail)." Metadata Keywords adds `chain_sha256=<...>` so any DMS auto-indexes.
  - **Visual treatment:** the chain PDF is *not* a courtroom statement — it is an audit artifact. Diagonal pale watermark "AUDIT TRAIL — NOT AN OFFICIAL REPORT" on every page; identifier stripe uses a different color from the signed report so they don't get confused in a file folder.
- **UX (per detective-review):** when the user clicks "Export PDF" on a signed report, the post-export action panel shows **both** files explicitly:
  - `📄 Eleanor Rush — final report.pdf` *Your official report — goes in the case file.*
  - `🔎 Eleanor Rush — audit trail.pdf` *SB-524 audit trail — for legal review.*
  - `[Download both]` button + a tooltip distinguishing the two. The detective doesn't have to know what a "chain of custody" is — the UI tells them.
- **Acceptance:**
  - Signed PDF + chain PDF generated as a pair on the same `POST /reports/{id}/export`; both downloadable independently via `GET /reports/{id}/pdf` and `GET /reports/{id}/chain.pdf`.
  - Chain PDF includes: source-doc inventory, media-input inventory, every message (incl. discarded re-asks, with refusal flags surfaced), every revision, every audit event.
  - Audit-integrity hash present in footer + metadata; reproducible by an auditor hitting the live chain endpoint.
  - First AI draft section visibly labeled "Not an officer statement (Penal Code §13663(b))."
  - Citation-coverage stats present and accurate.
- **Out of scope:** rendering source-document body content inside the chain (the chain *describes* the conversation that produced the signed text, not the source bytes — those live in the discovery package, F8).

### F8 — Discovery Package (per case, per report set)

- **What:** a ZIP bundle containing every artifact a defense motion, DA case package, or city-attorney subpoena would need for a named case (or subset of named reports): signed-report PDFs + chain-of-custody PDFs (from F7) + source-document & media-input pointer manifest + ZIP-level self-signing manifest. Delivered via short-lived signed URL to customer storage; **not retained by Cold Case after delivery.**
- **Why:** when a discovery motion or DA case package needs everything Cold Case has about one defendant — across one or many reports — manually assembling the bundle is error-prone. A single endpoint that emits a hash-pinned ZIP with a self-attesting manifest makes "give me everything you have on this case" a one-click answer.
- **Who uses it:** this is a **records-officer / city-attorney** workflow, not a frontline detective workflow. The UI exposes it as **"Export for discovery"** (not "Discovery Package" — courthouse jargon) under a collapsible **Compliance** section on the case detail page, and the button is **gated by the `case.export` permission** so detectives without that role see it as disabled or hidden.
- **Mechanism:**
  - `POST /cases/{id}/discovery-package` (body: optional `report_ids[]` to subset, optional `include_source_binaries=false`, optional `reason`). Synchronous up to ≤60s for a case with ≤20 reports; for longer assemblies, returns `{status: "preparing", job_id}` and the UI polls `GET /cases/{id}/discovery-package/{job_id}`.
  - Bundle contents:
    - `INDEX.txt` — plaintext, human-readable. Lists every file with one-line description.
    - `manifest.json` — machine-readable. Fields:
      - `coldcase_version`, `generated_at`, `requesting_user_id`, `requesting_user_display`, `reason` (free-text)
      - `case_number`, `case_id`, `report_ids[]`
      - `files[]` — every embedded file with `{path, sha256, size_bytes, kind}` where `kind ∈ {signed_report, chain_of_custody, source_document, media_input, readme, index}`
      - `documents[]` — every Document on the case `{filename, storage_uri, sha256, mime_type, size_bytes, registered_at}` (pointer-only by default)
      - `media_inputs[]` — every MediaInput on the case `{filename_or_descriptor, storage_uri, sha256, source_type, duration_seconds, captured_at, description}`. Required by §13663(c)(2) — defense counsel must see every media item the AI was shown.
      - `manifest_sha256` — `sha256(concat(file.sha256 for file in files[] sorted by path))`. Self-signing — anyone can verify by re-hashing the embedded files.
    - `reports/<report_id>.pdf` + `reports/<report_id>.chain.pdf` for each report (F7 outputs).
    - `documents/<sha256-prefix>__<filename>` — only when `include_source_binaries=true`; otherwise the source-document inventory lives in `manifest.json` as pointers.
    - `README.md` — explains the bundle structure + how to verify hashes via `sha256sum -c`.
  - **Data residency for source documents.** Cold Case **does not include source-document binaries** in the discovery ZIP by default — only their `(filename, storage_uri, sha256)` pointer records. Customer storage is the source of truth; if the discovery target needs the binaries, the customer ships them separately from their Azure/S3 with the same hashes for verification. Optional flag `include_source_binaries=true` writes the bytes to the ZIP for customers who'd rather have one self-contained artifact — but this requires explicit customer opt-in per case and produces a `case.discovery_exported` audit event with `included_source_binaries: true` flag for CJIS visibility.
  - **Delivery & retention (rule #21 below).** The ZIP is generated to a Cold-Case-controlled encrypted temp dir (NOT system `/tmp`), hashed, written to customer storage at the customer-provided URI, the signed URL is returned, and the temp file is unlinked synchronously after a successful write. On upload failure, the temp file is deleted after a 1-hour TTL; manual recovery requires `case.export_recovery` permission and emits an `AuditEvent`. The signed URL has a default TTL of 1 hour, is never logged to external observability systems, and is recorded in the audit event with its expiry only (the URL itself is hashed before log writes).
  - Audit: a `case.discovery_exported` event captures `{requesting_user_id, requesting_user_display, reason, report_ids, include_source_binaries, manifest_sha256, customer_storage_uri, signed_url_expires_at, signed_url_sha256}`.
- **UX:** a **Compliance** panel on the case detail page, collapsed by default, contains:
  - The "Export for discovery" button (disabled with tooltip if user lacks `case.export`).
  - A reason field (required — pre-populates the audit event).
  - A toggle "Include source documents in the ZIP" (default off, with a tooltip explaining the data-residency tradeoff).
  - A live preview of what's in the bundle: N signed reports, N chain PDFs, N documents, N media inputs.
- **Acceptance:**
  - Endpoint produces a ZIP for any case in under 60s for cases with ≤20 reports.
  - `manifest.json` is self-signing: re-computing `sha256(concat(file_hashes))` matches `manifest_sha256`.
  - `sha256sum -c` against the index passes for every embedded file.
  - Package opens cleanly in evidence.com and standard DMS tools.
  - Cold Case has no copy of the ZIP 60s after successful delivery; orphaned temp files (upload failure path) are cleaned within 1 hour.
  - The signed URL never appears in plaintext in any log line accessible outside the customer tenant.
- **Out of scope:** redaction of bundle contents (separate workflow); defense-counsel-direct download portal (customer fronts that); media transcription (the manifest lists audio/video but Cold Case doesn't transcribe).

### F9 — Officer's Editorial Work (first-draft vs signed diff)

- **What:** a side-by-side / unified diff that highlights every addition, deletion, and reordering the officer made between the §13663(b) verbatim first AI draft and the signed final text. Available in the UI (collapsible **"Officer's editorial work"** section on the report drawer) and as a printable PDF.
- **Framing (per detective-review):** this is **not** a "what you deleted" view. It is the **officer's professional editorial record** — the diff between what a tool produced and what a sworn officer signed. The UI language reinforces that editing is correct behavior:
  > *"Below is every change you made to the AI's first draft. Removing unsupported claims, verifying facts, and improving clarity are your professional responsibilities. The AI is a tool. Your signature means you reviewed everything and stand behind every claim that remained."*
- **Why:** §13663(b) draws a bright line — drafts are *not* the officer's statement; only the signed final is. The space between them is, by definition, the officer's work product. Under **Brady v. Maryland** (and California Evidence Code §1054.1), if the officer deleted exculpatory language the AI surfaced (e.g., "no defensive wounds were observed" → struck), that's discoverable for the defense. This view makes the delta inspectable in seconds — *both* for self-review by the detective before signing and for legal review afterward.
- **Mechanism:**
  - Server: `GET /reports/{id}/diff` returns a JSON unified-diff structure between `Report.first_ai_draft_text_snapshot` and the signed revision's text (the revision whose hash matches `signature.content_sha256`). Optional `?against=<seq>` lets the user diff against any revision (useful during pre-sign self-review).
  - Server: `GET /reports/{id}/diff.pdf` renders the diff as a print artifact. Self-identifies with the same Report ID footer stripe + audit-integrity hash as the chain PDF.
  - UI: in the report drawer, add a "Officer's editorial work" collapsible section alongside "§13663(b) first AI draft" and "Revision history". Default-collapsed.
  - **Color treatment (per UX review):** use **neutral colors with explicit labels**, not red/green which carry good/bad valence. Recommend **blue underline** for "officer added" + **gray strikethrough** for "officer removed from AI draft", with text labels `+ officer added →` and `− AI wrote (you removed) ←` prefixed to each delta paragraph.
  - **PDF watermark:** "OFFICER'S EDITORIAL WORK — NOT AN OFFICIAL REPORT" diagonal watermark on every page. Header reads "Editorial History (Penal Code §13663(b) work product)."
  - The diff is computed on every render (cheap — `difflib.ndiff` over reasonable-size text) so it always reflects the current signed text. **The diff is never cached as a separate artifact** — both ends already live on the Report row, and the diff is derivation-only. This is deliberate (rule #17 corollary): no new persistence surface.
- **Acceptance:**
  - Diff endpoint returns correct unified-diff for any signed report against its first AI draft.
  - PDF export renders cleanly with the neutral color + labeled treatment and the editorial-work watermark.
  - When run against a report where the officer made no edits, the diff is empty and the UI says *"Officer signed the AI's first draft verbatim — no edits."*
  - When run against a still-in-draft report, the UI shows the diff against the current `final_text` (helps the officer self-review before signing).
  - The diff response is never stored on disk or in a cache table; recomputed per request.
- **Out of scope:** semantic / NLP "you removed an exculpatory claim" classifier (Phase 2 idea — see §13); supervisor sign-off on diffs above a threshold (Phase 2); semantic counts ("you removed N sentences from the AI!") — explicitly excluded to avoid creating perverse incentives to under-edit.

### F15 — Per-Case Audit Manifest PDF

- **What:** a single PDF that summarizes everything Cold Case knows about a case at audit time. Distinct from F7 (one chain per report) — F15 is the case-level rollup. Contents: case header (number, title, classification, retention, status), a one-row-per-report table (id, title, status, signer, signed_at, content_sha256, AI program(s) used, citation count, citation coverage %), source-document inventory with hashes, MediaInput inventory (§13663(c)(2)), distinct AI programs across the case, audit-event counts by type, and a "verify any report's chain" footer that names the per-report chain endpoint.
- **Why:** when the city auditor opens "Q3 2026 review" they want one page that says *here's case CRRA-1954-RUSH, here are the 4 reports we wrote on it, here's the retention picture, here's who signed each, here's every model that touched it*. F7 chains are per-report. F15 is per-case. Both will get bundled together in F8 discovery packages, but F15 stands alone for routine audit.
- **Mechanism:**
  - New module `services/case_manifest_export.py` reuses ReportLab + the styling from `chain_export.py`. Renders a 2–4 page PDF.
  - `GET /cases/{id}/audit-manifest.pdf` — generated on demand, cached at `uploads/manifests/<case_id>.manifest.pdf`. Regenerated if cache is missing or stale (case.last_activity_at newer than file mtime).
  - Self-identifying footer: case number + tenant id + generated_at. PDF metadata Subject: "Cold Case — case audit manifest".
- **Acceptance:**
  - For any case with ≥1 signed report, the manifest renders cleanly with all sections populated.
  - The reports table cites every signed report's AI programs + citation coverage stats matching what F7's chain reports.
  - For a case with 0 signed reports, the PDF still renders with "(no signed reports yet)" placeholders so a "show me an empty case" view is possible.
- **Out of scope:** redaction; cross-case rollups (those are F16 and a future "agency dashboard"); historical snapshots of the manifest at a past date.

### F16 — AI Program Inventory

- **What:** a tenant-scoped report that lists every distinct AI program version used in any signed report, with usage counts and a sample report id per program. Filterable by date range.
- **Why:** California SB-524's expected oversight cadence is a state attestation: "tell us every AI you used last year and how many official reports it produced." Today Cold Case captures the model snapshot id on every Message + every Report.ai_programs_used. F16 is the aggregation.
- **Mechanism:**
  - `GET /audit/ai-programs?since=<iso>&until=<iso>` — returns `[{name, version, provider, report_count, first_used, last_used, sample_report_id}]` sorted by `report_count desc`.
  - Implementation: MongoDB aggregation over `Report.ai_programs_used`. No new schema.
  - UI: a table on the Audit page (already exists) with a date-range picker.
- **Acceptance:**
  - Returns rows only for signed reports (drafts / unsigned excluded — they didn't produce a §13663 artifact).
  - Date-range filter applies on `Report.signed_at`.
  - For each row, the sample_report_id resolves to a real Report the auditor can click into.
- **Out of scope:** breakdown by officer (Phase 3); cost / token usage (no business need); per-month time-series chart (would be nice; defer).

### F17 — Refusal & Anomaly Report

- **What:** a filtered view of audit events flagged for human review: every `MESSAGE_ASSISTANT` event with `detail.refusal_detected=true` and every `VENDOR_ACCESS` event. Helps the city auditor + internal QA spot patterns of model regression and patterns of vendor-staff access.
- **Why:** today these events are persisted but invisible unless someone knows to filter. Making them a first-class report converts background noise into actionable signal.
- **Mechanism:**
  - `GET /audit/anomalies?since=...&until=...` returns a structured payload with two sections: `refusals[]` (each from an assistant message) and `vendor_access[]` (each from a vendor-access event, when F10 lands). Each row links to the case + report + conversation for drill-down.
  - UI: add an "Anomalies" tab to the Audit page; default date range = last 30 days.
- **Acceptance:**
  - Returns zero rows when nothing has gone wrong (the desired steady state).
  - Each refusal row carries: timestamp, user, case, conversation, message id, the refusal phrase that matched, AI model id, prompt-token count.
  - Each vendor-access row carries: timestamp, requesting Darwin operator, purpose, scope, approval status.
- **Out of scope:** automated remediation (e.g., auto-rerun the prompt against a stronger model); alerting on threshold breaches.

### F10 — Vendor Access Portal (statutory: §13663(d) enforcement)

- **What:** a request-and-approve workflow that records every time Darwin operations staff need to access agency data under one of the §13663(d)(iii) carve-out purposes (troubleshooting, bias mitigation, accuracy improvement, system refinement). Today rule #9 is contract-only; F10 makes the contract enforceable in software so a city attorney can audit "show me every time a Darwin engineer touched our data in 2026."
- **Why:** the statutory reviewer flagged this as the only conspicuous §13663 gap that F7/F8/F9 didn't close. Without it, vendor compliance is unverifiable post-hoc.
- **Mechanism:**
  - **New model `VendorAccessRequest`** (in `models/vendor_access.py`):
    - `id`, `tenant_id` (the agency whose data is being accessed)
    - `requesting_operator_id` (Darwin engineer), `requesting_operator_display`
    - `purpose` ∈ {`troubleshooting`, `bias_mitigation`, `accuracy_improvement`, `system_refinement`}
    - `reason_detail` (free text — required, e.g. "investigating intermittent OCR failure reported in ticket #142")
    - `scope` — either `tenant_wide` or `case_ids: [str]` or `report_ids: [str]`
    - `requested_at`, `approved_by` (agency admin id), `approved_at`, `denied_by`, `denied_at`, `denial_reason`
    - `expires_at` (defaults to 24h after approval)
    - `status` ∈ {`pending`, `approved`, `denied`, `expired`, `revoked`}
    - `accessed_at[]` — append-only timestamps each time the operator used the approved access during the validity window
  - **New endpoints:**
    - `POST /vendor/access-requests` — Darwin operator opens a request (tenant_id, purpose, reason_detail, scope, expires_in_hours)
    - `GET /vendor/access-requests` — list, filterable by status / scope. Agency-side admin sees all requests against their tenant; Darwin operator sees their own
    - `POST /vendor/access-requests/{id}/approve` — agency admin only
    - `POST /vendor/access-requests/{id}/deny` — agency admin only, must supply `denial_reason`
    - `POST /vendor/access-requests/{id}/revoke` — agency admin can revoke an already-approved request mid-window
    - `POST /vendor/access-requests/{id}/record-access` — the Darwin operator pings this from their tooling each time they actually pull data, recording the timestamp + a short note. Hard-fails (403) if status ≠ `approved` or `expires_at < now`
  - **New audit event types:** `VENDOR_ACCESS_REQUESTED`, `VENDOR_ACCESS_APPROVED`, `VENDOR_ACCESS_DENIED`, `VENDOR_ACCESS_REVOKED`, `VENDOR_ACCESS_USED`. Each carries the request id + scope + purpose + operator identity.
  - **UI:**
    - Admin route `/admin/vendor-access` (gated by `audit.read` permission — same role the city attorney uses) renders the request queue, with approve / deny / revoke action buttons.
    - A pending-request count badge appears on the admin nav when any request is awaiting approval.
  - **Permissions:**
    - New permission `vendor_access.request` — Darwin operator role
    - New permission `vendor_access.approve` — agency admin only (typically the city attorney or designated records officer)
    - The agency admin DOES NOT need `vendor_access.request` — separation of duties
- **Acceptance:**
  - End-to-end smoke: operator submits request → agency admin approves → operator pings `record-access` (succeeds) → expires_at passes → next `record-access` fails 403 → status auto-flips to `expired`.
  - The F17 anomaly report includes every `VENDOR_ACCESS_*` event with the right structure.
  - The audit event stream is queryable by `event_type=vendor.access.used` for the auditor.
  - A new audit-summary row on each Case shows "Vendor accesses against this case: N" so a city attorney reviewing the case sees the history at a glance.
- **Out of scope (Phase 3):** automated approval routing based on purpose × scope; integration with Darwin's internal ticket system; per-operator activity dashboards.

### F18 — Permission enforcement on every endpoint

- **What:** every API route checks the caller holds the permission named in `auth/app_manifest.py`. Default-deny: a route that hasn't declared its permission requirement returns 403. Today permissions are declared but unenforced — `tenant_id` is the only gate, which means any authenticated user in a tenant can do anything.
- **Why:** §13663(a)(2) signing identity has to be attributable; if every user can sign every report, the attestation is unenforceable. Same for `case.export` (Brady-relevant discovery), `audit.read` (city-attorney access), `vendor_access.approve` (separation of duties with operators).
- **Mechanism:**
  - Each router function declares its required permission via a `requires(permission)` dependency or wrapper.
  - The Launchpad Admin `UserContext` already carries the resolved permission set; the dependency fails the request 403 if the permission isn't in the set, logs a `PERMISSION_DENIED` audit event with `{path, method, permission_required, user_id}`.
  - Dev-bypass user keeps `admin` role → all permissions; no behavior change in dev.
  - Two **new** permissions added to the manifest: `vendor_access.request` (Darwin operator role) and `vendor_access.approve` (agency admin only — separation of duties from `case.read` so a sergeant approving a vendor request can't also fulfill it).
- **Acceptance:** A user with the `viewer` role gets 403 on `POST /reports/{id}/sign`, `POST /cases/{id}/discovery-package`, and `POST /vendor/access-requests/{id}/approve`. The dev user keeps the same behavior as today.

### F19 — Authenticated signing identity (§13663(a)(2) hardening)

- **What:** the officer's signature on a Report derives `user_id`, `display_name`, and `ip_address` from the authenticated `UserContext`, not from the request body. The `badge_number` is the only field the body controls, and it's recorded alongside the user_id so an auditor can verify it.
- **Why:** today anyone with the session can type "Det. K. Walker" + badge "WALKER-1" into the sign form and produce a §13663(a)(2) attestation that names them. Cross-examination would break this in 30 seconds. Real ESIGN/UETA flows require the signature identity = the authenticated session.
- **Mechanism:**
  - `POST /reports/{id}/sign` body shape changes from `{display_name, badge_number, attestation_text}` to `{badge_number, attestation_text?}`. `display_name` is removed; the server uses `user.display_name`.
  - `OfficerSignature.user_id`, `display_name` always derive from `UserContext`.
  - Phase 4 will move `badge_number` onto a user-profile record so it doesn't even live in the body; for now we keep it body-supplied but the audit event records `{authenticated_user_id, claimed_badge}` so any mismatch is reviewable.
- **Acceptance:** Smoke test attempts to sign with a body that names a different officer; server ignores the field and stamps `user.display_name`. Audit event records the resolved values.

### F20 — Vendor access scope enforcement (§13663(d) runtime gate)

- **What:** when a request is made by a Darwin operator with an active `VendorAccessRequest`, every case/report/conversation reference in the path is checked against the request's `scope_kind` and `scope_case_ids` / `scope_report_ids`. Off-scope access returns 403 and emits a `VENDOR_ACCESS_SCOPE_VIOLATION` audit event.
- **Why:** F10 today *logs* approved access but doesn't *enforce* the declared scope. An operator approved for `case_ids=[X]` can still hit `/cases/Y` because the only check is tenant match. Without runtime enforcement, F10 is theater.
- **Mechanism:**
  - New `services/vendor_scope.py::resolve_active_scope(user) -> ActiveScope | None`. Returns the approved+unexpired+unrevoked `VendorAccessRequest` for this operator+tenant, or None (means non-operator or no active access).
  - New FastAPI dependency `require_vendor_in_scope(case_id_param, report_id_param, ...)` that, when ActiveScope exists, asserts the path's case/report ids fall within scope.
  - Applied to: cases/* (case_id path param), reports/* (report_id), conversations/* (joined via case), discovery-package/*, audit/cases/*.
  - For `tenant_wide` scope, the dependency is a no-op (allows everything in the tenant).
- **Acceptance:** Operator with approved `case_ids=[X]` scope can hit `/cases/X/...` but `/cases/Y/...` returns 403 + audit event. Same operator with `tenant_wide` scope can hit any case.

### F21 — Real document upload (multipart)

- **What:** `POST /cases/{id}/documents/upload` — multipart endpoint that takes a binary file, writes it through the `ArtifactStore`, computes sha256, registers the Document with the resulting storage URI. Replaces today's "Register document" form that only accepts an existing-on-server filename string.
- **Why:** Detective Gaudi's actual workflow is "I have a patrol-report PDF on my desktop, drag it into Cold Case." Today we can't run a pilot — every demo document has to be pre-seeded server-side.
- **Mechanism:**
  - Backend: `POST /cases/{id}/documents/upload` accepts `UploadFile` + optional mime/description. Stream-hashes while writing; rejects > 50 MB by default (configurable via env). Document record's `storage_uri` is the artifact-store key (`uploads/<case-id>/<sha256>__<filename>`), `sha256` is the streamed hash.
  - Frontend: `<input type="file" accept="application/pdf,image/*">` in the document sidebar; submits as multipart; on success the new document appears in the list with its extraction badge.
  - File names sanitized: directory traversal characters stripped; final filename safe for sha256-prefixed naming.
- **Acceptance:** Detective drags a PDF onto the upload UI → file uploads → appears in document list → chat with case sees it via implicit-context rule. No pre-seeding.

### F22 — Retention sweeper

- **What:** scheduled job that purges audit data past its case's effective retention. Respects rule #10 (first-AI-draft retention floor — never purge a `Message` flagged `is_first_ai_draft` while its parent Report is still retained). Writes a `RETENTION_PURGED` audit event with a manifest of what was deleted.
- **Why:** today `Case.retention_policy` is set on case create but never consulted. PRD §F5 claims §13663(b) retention is enforced; in reality nothing prunes when retention expires.
- **Mechanism:**
  - `services/retention_sweeper.py::sweep_case(case)` — for one case, compute the effective retention end date; if past, identify Conversations/Messages/AuditEvents to purge; delete with guard against first-draft Messages whose Report retention is still active.
  - `services/retention_sweeper.py::sweep_all()` — iterate every Case in every tenant.
  - `POST /admin/retention-sweep` — manual trigger (gated by `admin.view` permission). Returns a summary `{cases_scanned, conversations_deleted, messages_deleted, audit_events_deleted, first_drafts_preserved}`.
  - Phase 4: wire a docker-compose cron service or APScheduler to run nightly. For now manual trigger is sufficient for compliance demonstration.
- **Acceptance:** A case marked `retention_policy=2y` and closed >2y ago has its conversations/messages purged on sweep. A case marked `indefinite` is untouched. A first-AI-draft Message whose Report is still retained is preserved even if the conversation otherwise qualifies for purge.

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
16. **OCR fallback for image-only PDFs (text-extraction mode only).** When `COLDCASE_LLM_MULTIMODAL=false` (the legacy dev path used by the mock Ollama provider and any pre-multimodal model), `services/document_text.extract_text` tries `pypdf` first; if the embedded text layer averages fewer than `COLDCASE_OCR_MIN_CHARS_PER_PAGE` non-whitespace characters per page (default 40), it falls back to OCR via `pymupdf` + `pytesseract.image_to_string`. Results are memoized per immutable document version. Pattern mirrors the sibling `ada` project's WCAG remediation pipeline. **In multimodal mode (rule #17) this entire path is bypassed** — the LLM reads the PDF natively.

17. **Data residency: source-document binaries never persist on Cold Case (multimodal mode).** When `COLDCASE_LLM_MULTIMODAL=true` and the active LLM provider declares `supports_attachments=True` (OpenAI's gpt-4o / gpt-5.x families, and the future GCC Copilot provider), Cold Case streams each in-context document's bytes inline to the LLM at request time as an `input_file` part. The bytes live only in the request stack frame for the duration of one chat call — Cold Case does NOT extract, OCR, or cache the text, does NOT upload to an OpenAI Files slot, and does NOT log document bodies in audit events. The document body is held only in (a) the customer's primary storage (Azure Blob / S3 / SharePoint), and (b) ephemerally in the LLM provider's request handler for one inference. Cold Case persists only: `storage_uri`, `sha256`, `original_filename`, `mime_type`, `size_bytes`, and the audit lineage of prompts + responses + citations.

    **Carve-out for Cold Case-authored audit artifacts.** Cold Case-generated artifacts that exist because the statute requires us to retain them — the §13663(b) first-AI-draft snapshot, the signed-report PDF (F3), the chain-of-custody PDF (F7), the report revisions (F3a), and on-demand-derived views like the editorial-work diff (F9) — are NOT subject to rule #17. They are required outputs of the audit obligation itself, retention-bound to the Report (rule #14) and the case retention policy (F5). The discovery-package ZIP (F8) IS subject to rule #17 — it is transient and not retained by Cold Case after delivery.

    Citations switch from line-anchored (`[src: file, L<n>]`) to page+quote (`[src: file, p<page>, "<verbatim quote>"]`) so that verification works against the source PDF without any Cold Case-side text mirror. Phase B (future) replaces the local-fs `LocalDocumentStorageProvider` with a customer-storage adapter, eliminating the upload-to-disk step entirely.
18. **Signed report and chain-of-custody PDF travel as a pair.** Every `POST /reports/{id}/export` produces TWO PDFs in the same operation: `<report_id>.pdf` (the signed report under §13663) and `<report_id>.chain.pdf` (the printable chain of custody under §13663(c)). Both are linked from the Report and both are pushed to evidence.com (or whatever destination the customer configured) as a pair. The chain PDF must not be alterable without re-export, and an auditor with only the chain PDF can resolve back to the live audit endpoint via the Report ID printed in its footer.
19. **Discovery packages do not persist on Cold Case.** When a `case.discovery_exported` request fires (F8), Cold Case generates the ZIP to a temp dir, writes it to customer storage at a customer-provided URI, returns a short-lived signed URL, and unlinks the local temp file. The ZIP's `manifest.json` is self-signing (a hash over the concatenated file hashes), so any party can verify the bundle's integrity without trusting Cold Case to retain it. Source-document binaries are included only when explicitly requested via `include_source_binaries=true`; default is pointer-only.
20. **The diff between AI first draft and signed report is the officer's work product.** F9 makes this delta available as a JSON diff and a printable PDF. Under Brady, if the officer deleted exculpatory language the AI surfaced, that change is visible in the diff. The diff itself is not an "official report" — it's an audit artifact, watermarked accordingly. The diff is computed on demand and never cached as a separate artifact (no new persistence surface).
21. **Discovery-package temp files have a cleanup contract.** Any F8 ZIP assembly that requires temp-disk space writes to a Cold-Case-controlled directory (not system `/tmp`). On successful write to customer storage, the temp file is unlinked synchronously in the same transaction. On upload failure, the temp file is deleted after a 1-hour TTL; manual recovery is permission-gated (`case.export_recovery`) and emits an `AuditEvent`. Signed URLs returned to the requester have a default 1-hour TTL, are never logged in plaintext to external observability systems, and have their `sha256` (not their value) recorded on the `case.discovery_exported` audit event for traceability.
22. **Adjacent California statutes acknowledged.** Cold Case retention defaults are designed to satisfy the floor set by **Government Code §34090** (records retention for local agencies — generally 2+ years for police records, longer for homicide). Discovery exports (F8) are timed and structured to satisfy **California Evidence Code §1054.1** (formal pre-trial discovery obligations of the prosecution) and to enable prompt **Brady v. Maryland** disclosure of exculpatory material — the F9 editorial-work diff is the primary surface for that latter obligation.
23. **Vendor access is logged before it happens, not after (§13663(d) enforcement).** Any Darwin operations engineer who needs to access agency data under one of the §13663(d)(iii) carve-out purposes must, *before* accessing, open a `VendorAccessRequest` (F10) with: explicit purpose category, free-text reason detail, scope (case ids or tenant-wide), and a requested expiry. The request remains in `pending` status until an agency admin (typically the city attorney or designated records officer) `approve`s or `denies` it. Each actual data pull during the validity window pings `record-access` to leave a usage timestamp. After `expires_at` or `revoke`, further `record-access` calls hard-fail 403 and the request auto-flips to `expired`. **F20** adds runtime scope enforcement: every case/report path parameter is checked against the operator's approved scope; off-scope access returns 403 and emits a `VENDOR_ACCESS_SCOPE_VIOLATION` audit event. This converts §13663(d) from a contractual promise to a per-request, per-use, per-tenant audit trail the city attorney can subpoena directly.
24. **Permission default-deny (F18).** Every API route declares the permission it requires (from `auth/app_manifest.py`). The Launchpad Admin `UserContext` is consulted on every request; absent the named permission, the route returns 403 and emits a `PERMISSION_DENIED` audit event. Routes that haven't declared a requirement are treated as admin-only (`admin.view`) to fail safe. This applies even when `IS_DEV_BYPASS_AUTH_ENABLED=true` — the dev user simply happens to hold the `admin` role.
25. **Officer signing identity is authenticated, not body-supplied (§13663(a)(2) hardening).** `OfficerSignature.user_id` and `.display_name` are derived from the resolved `UserContext`. The signing endpoint body retains `badge_number` (recorded alongside `user_id` for auditor verification) and an optional `attestation_text` override, but never `display_name`. An attempt to pass `display_name` in the body is ignored and the server-side value is used.
26. **Document upload writes through the artifact store (F21).** `POST /cases/{id}/documents/upload` is the supported way to add a binary to a case. The upload is stream-hashed, written through `services/artifact_store.put`, and registered as a Document whose `storage_uri` is the artifact-store key. Today the default `LocalArtifactStore` writes to the docker volume; in Phase B the customer-storage adapter routes the bytes to Azure Blob / S3 / SharePoint without changing the call site.
27. **Retention purge respects the first-draft floor (F22).** A scheduled sweeper iterates every Case, computes the effective retention end date, and purges Conversations / Messages / AuditEvents past that date. The sweeper NEVER deletes a Message whose `is_first_ai_draft=true` if the parent Report's retention is still active (rule #10). Each sweep emits a `RETENTION_PURGED` audit event listing what was deleted; the event itself is exempt from the next sweep.

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
| **(c)(1)** | Audit trail identifies the person who used AI | Every Message has `user_id`; every Report has `signed_by`; AuditEvent stream is per-user. F4 surfaces this; F7 prints the full chain as a courtroom-grade PDF; F8 bundles all chains for a case | §5/F4, §5/F7, §5/F8, §6 |
| **(c)(2)** | Audit trail identifies video/audio footage used as input | `MediaInput` entity, linked to Conversation + Report | §6, §7/#7 |
| **(d)** | Vendor cannot share/sell/otherwise use agency data except for agency, court order, or troubleshooting/bias/accuracy/refinement | **F10 Vendor Access Portal**: `VendorAccessRequest` model + approve/deny/revoke/record-access endpoints + 5 audit-event types. Combined with business rule #9 (contractual) + rule #23 (per-request lifecycle), §13663(d) is now both contractually and software-enforceable. F17 Anomaly Report surfaces every `vendor.access.used` event for routine review | §5/F10, §7/#9, §7/#23, §5/F17 |
| **(e) — "AI" definition** | Systems that "infer from the input it receives how to generate outputs" — covers narrative-drafting + generative report enhancement | All Copilot interactions are in scope. Documented in `services/llm_provider.py` | §8 |
| **(e) — "official report" definition** | The **final version** signed by the officer | `Report` entity is "official report"; pre-sign drafts are not | §6, §7/#5 |
| **(e) — "first draft" definition** | The initial document or narrative produced **solely by AI** | `Message.is_first_ai_draft` set only on the assistant Message before any officer edit | §6, §7/#3 |

### Statute-driven test cases (must pass before any agency goes live)

Status legend: ✅ = automated smoke test passes locally; ⏳ = not yet covered.

1. ✅ Export a Report; open the PDF; **every page** contains the verbatim disclosure string + at least one AI program name. (Smoke test #12–#13 — `pypdf` extraction confirms text on both rendered pages.)
2. ✅ Attempt to mutate the `first_ai_draft_message_id` Message → API returns 403 and writes a `FIRST_DRAFT_MUTATION_BLOCKED` AuditEvent. (Closed in v0.8.0 — `PATCH /messages/{id}` always 403s + audits when `is_first_ai_draft=True`; non-first-draft messages return 405. Verified in `scripts/compliance-smoke.sh`.)
3. ✅ Attempt to export a Report without signing → API returns 422 referencing §13663(a)(2). (Smoke test #9.)
4. ⏳ Mark a Case closed with retention `match_official_report`; attempt to purge any Message that is a first AI draft → purge skipped, AuditEvent emitted. (Purge job not yet implemented.)
5. ✅ Audit export for a Report renders the full Conversation tree with first draft labeled "First AI draft — not an officer statement (§13663(b))". (Smoke test #14.)
6. ⏳ Vendor-side admin attempts to view a prompt body → blocked unless logged under `vendor_access` with operator id + reason. (Vendor-side admin surface not yet built.)
7. ✅ AI program identification in the export matches the `model` field recorded on the `first_ai_draft` Message. (Smoke test #7, #15.)
8. ✅ Same Message cannot be promoted twice → 409. (Smoke test #8.)
9. ✅ Homicide classification on case-create auto-suggests indefinite retention. (Smoke test #2.)

## 13. Out-of-scope for MVP / Phase 2 candidates

### Adjacent statutes & frameworks not directly addressed by MVP

- **CJIS-policy compliance** of the GCC Copilot endpoint — that's the agency's M365 GCC posture, not Cold Case's.
- **Government Code §34090** records-retention floors — Cold Case's retention defaults satisfy §13663(b) and are configurable per-case (F5); the agency owns the broader records-retention policy.
- **Evidence Code §1054.1** formal pre-trial discovery cadence — Cold Case provides the artifacts (F8 discovery package, F9 diff) but doesn't drive the §1054.1 timeline; that's the DA's workflow.
- **Public Records Act** request workflow — Cold Case stores the data a PRA request would draw from; the request portal lives elsewhere.

### Phase 2 features (planned, not in this batch)

- **F11 — Detective playground.** An ephemeral "scratch" conversation that lets the detective experiment with prompts before committing them to the auditable record. Trade-off: §13663(c) audit-trail strength wants every prompt logged. F11 design: scratch lives ≤24h and is auto-pruned, OR remains in the chain but is flagged "scratch / pre-promotion" so the city attorney can filter it out. Open question for legal review.
- **F12 — Second-opinion workflow.** Re-run the same prompt against a different model (e.g., gpt-5.5 ↔ a Claude or GCC-Copilot deployment) to surface inter-model disagreement. Important for high-stakes cases (homicide) where hallucination risk justifies the cost.
- **F13 — Semantic-change classifier on F9 diff.** Flag the diff segments that match patterns like "officer removed an AI-noted uncertainty" or "officer added an unsourced claim", so the auditor's eye is drawn to high-Brady-relevance changes. This is the natural next step after F9.
- **F14 — Inline penal-code lookup** in the chat panel — sidebar quick-ref to CalCrim instructions and applicable Penal Code sections without leaving Cold Case.
- **Log scrubbing for vendor diagnostics.** Any error/diagnostic event shipped to Darwin-side observability is redacted: cited text removed from `[src: ...]` tokens, case numbers hashed, officer names removed. Raw logs stay on the agency's secure backend, accessible only to agency admins and via court order. Captured here as a runbook obligation; will be operationalized when we have a real observability surface.

## Changelog

| Version | Date | Changes |
|---|---|---|
| 0.10.0 | 2026-05-20 | **Hypothesis workflow (voice-first brain dump → AI structuring → cross-check).** New artifact pair: `BrainDump` (raw input: typed / in-portal recording / dropped audio file, with audio kept through the case's normal retention) and `Hypothesis` (status-tracked working theory with embedded `HypothesisFinding`s for supporting / contradicting / gap evidence). Endpoints: POST `/cases/{id}/brain-dumps` (typed), POST `/cases/{id}/brain-dumps/audio` (multipart MediaRecorder OR drag-drop, .m4a/.mp3/.wav/.webm/.ogg/.aac/.flac up to 50 MB, transcribed via the new `providers/transcription.py` seam), PATCH for transcript edits, POST `/cases/{id}/brain-dumps/{id}/suggest-hypotheses` (LLM extracts up to 6 falsifiable claims with rationale), POST `/cases/{id}/hypotheses` (accept candidate → status=investigating), PATCH for status transitions (investigating → confirmed / disproved / superseded), POST `/cases/{id}/hypotheses/{id}/check` (LLM cross-references case docs and returns supporting / contradicting / gap findings), POST `/cases/{id}/hypotheses/{id}/findings` (accept one finding into the hypothesis record). 7 new audit-event types covering the full lifecycle. **Transcription provider seam**: Mock (default), OpenAI Whisper, LocalWhisper stub — agencies pick on-prem when they go live; officer audio doesn't have to leave the network. **New 8th case-workspace tab** "Hypothesis" with three-mode composer (Type / Record / Upload), editable transcript step before AI extraction (so the detective fixes proper nouns Whisper missed), suggestion review with accept-each Investigate / Dismiss, then a per-hypothesis card with status selector, evidence check, and pending-findings review |
| 0.9.0 | 2026-05-20 | Same-day follow-on after 0.8.0. **Refactor:** CaseDetailPage 2,648 → ~750 lines via four tab extractions (`src/features/cases/tabs/{Brief,People,Timeline,Chain}Tab.tsx`); zero behavior change, typecheck + build green at every step. **Dashboard cross-case insights:** new `GET /dashboard/insights` aggregates recurring people (loose name match across the caller's cases) + Jaccard-similar case pairs, rendered as a card between RecentActivity and MyCases — the cross-case graph data finally has a real entry point. **AI inferred-mention extraction** (Phase C closure): `POST /cases/{id}/persons/inferred-mentions` finds people *referenced but not named* ("the gas station attendant", "a man in a red truck") with rationale + exact excerpt + source doc; companion `/accept` endpoint persists the clue as a case-scoped Note and fires `INFERRED_MENTION_ACCEPTED_FROM_AI` on the hash chain. UI panel sits beside the existing named-Person AI suggester on People tab; saved items leave the list and a green confirmation banner links to the Brief tab where the new note lives. **Bug fix:** axios timeout 10s → 60s — the inferred-mention call (8–15s on multi-doc cases) was timing out silently, breaking every AI suggester through the shared client when the LLM took its time. **Cross-tab routing:** `?tab=<id>` now switches active case tab so cross-feature links can land where they mean to |
| 0.8.0 | 2026-05-20 | Single-session push covering Phase A workspace, Phase B tags + people + timeline + notes, Phase C AI extraction, hash-chained audit integrity, AI provenance, and graph. **§13663 hardening:** preflight (7 checks at `/admin/compliance/preflight`), retention scheduler actually running daily (was dead code), `PATCH /messages/{id}` 403 + `FIRST_DRAFT_MUTATION_BLOCKED` audit on first-draft mutation attempts (closes §12 test case #2), real hash-chained `AuditEvent` (`sequence` + `prev_event_hash` + `event_hash`) with tamper-detection verified live, `*_ACCEPTED_FROM_AI` audit events. **Detective workspace:** 7-tab case workspace (Brief / Evidence / People / Timeline / Reports / Chain / Export) with persistent chat panel; report workspace promoted out of drawer to its own route; dashboard at `/`; CSS cascade fix unblocking Tailwind v4 utilities across the whole app. **Phase B artifacts:** `Tag` + `TagAssignment` (closed agency vocab, 8 seeded), `Person` (role-grouped, manual + AI), `TimelineEntry` (manual + AI), `Note` (freeform scratch), `Provenance` embedded doc reused on Person + TagAssignment. **Phase C AI extraction:** tag / person / timeline-event / next-step suggesters — all closed-vocab, grounded, accept-each-individually, with provenance on accepted artifacts. **Graph:** Connections panel (1-hop case-overlap), two-hop co-occurrence network, Jaccard similar-cases, document mention finder (substring scan, Person → exact doc + line). **Legal artifacts:** `docs/legal/agency-policy-template.md` (880 lines), `docs/legal/vendor-data-handling-clause.md`, `docs/legal/compliance-status.md` (city-attorney-readable gap assessment). **Evidence.com data readiness:** `external_id`, `agency_ori_snapshot`, `date_of_incident`, `evidence_com_asset_id` (reserved). 11 commits, all on `main`. Compliance smoke 12/12, audit chain 715+ events / 0 breaks, prod build clean |
| 0.7.0 | 2026-05-11 | Phase 3 pilot-blocking hardening identified during workflow review. **F18** — permission enforcement on every endpoint (Launchpad Admin `requires_permission` dependency; default-deny; PERMISSION_DENIED audit event; two new perms `vendor_access.request` + `vendor_access.approve`). **F19** — `OfficerSignature.display_name`/`user_id` derived from authenticated UserContext, not request body (§13663(a)(2) hardening; ESIGN/UETA alignment). **F20** — vendor scope enforcement at runtime (operator with approved scope=case_ids hits off-scope case → 403 + VENDOR_ACCESS_SCOPE_VIOLATION event). **F21** — real multipart document upload through ArtifactStore. **F22** — retention sweeper with first-draft floor preservation. Business rules #24–#27. PRD review focused on pilot-readiness, not statutory coverage |
| 0.6.0 | 2026-05-11 | F10 Vendor Access Portal closes the only conspicuous §13663(d) gap from the v0.5.0 reviewer pass — new `VendorAccessRequest` model + request/approve/deny/revoke/record-access endpoints + 5 audit-event types + admin route. F15 Per-Case Audit Manifest PDF for case-level rollup (sibling to F7 chain PDFs). F16 AI Program Inventory for SB-524 annual attestation. F17 Refusal & Anomaly Report surfaces refusal_detected + vendor.access events. Business rule #23 added (vendor-access lifecycle). §12 (d) row upgraded from "Phase 2 idea" to shipped |
| 0.5.0 | 2026-05-11 | F7 (chain-of-custody PDF auto-paired on export, with media inventory + refusal flags + citation-coverage stats + audit-integrity hash), F8 (discovery-package ZIP with self-signing manifest, signed-URL handoff to customer storage, role-gated "Export for discovery" UI), F9 (officer's-editorial-work diff with neutral color treatment and Brady-aware framing). Business rules #17 clarified (audit-artifact carve-out), #21 added (temp-file cleanup), #22 added (adjacent CA statutes acknowledged). §13 reorganized into out-of-scope vs Phase 2 (F10 vendor portal, F11 playground, F12 second-opinion, F13 semantic diff classifier, F14 inline penal-code lookup, log scrubbing). PRD reviewed by three subagents (statutory completeness, data-residency/threat-model, detective UX) before lock |
| 0.4.0 | 2026-05-11 | Backend MVP landed: domain models, LLM + DocumentStorage provider seams, F1/F2/F3/F4 routers, §13663-compliant PDF export. End-to-end smoke (17 steps incl. 9 statute-driven checks) green |
| 0.3.0 | 2026-05-11 | SB-524 / Penal Code §13663 statutory mapping; added Report entity + MediaInput; rewrote business rules and F3 around first-AI-draft + statutory disclosure text; added §12 compliance matrix |
| 0.2.0 | 2026-05-11 | Requirements extracted from use-case interview (`docs/usecase-transcript.txt`) |
| 0.1.0 | 2026-05-11 | Initial scaffold from launchpad-starter-kit |
