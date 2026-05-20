# Model Agency Policy — Use of Artificial Intelligence in Official Reports

**Agency:** [AGENCY NAME] (model jurisdiction: Hopkinsville Police Department)
**Policy number:** [POLICY NUMBER]
**Effective date:** [EFFECTIVE DATE — must be on or after 2026-01-01]
**Last reviewed:** [YYYY-MM-DD]
**Adopting authority:** Chief of Police, [AGENCY NAME], in consultation with the City Attorney of [JURISDICTION]
**Statutory basis:** California Penal Code § 13663 (added by SB 524, 2025 Reg. Sess., Stats. 2025, ch. ___; effective January 1, 2026)
**Supersedes:** [PRIOR POLICY OR "None"]

> **City Attorney adoption note.** This template is offered as a model
> only. The agency's city attorney is responsible for confirming that
> the final adopted version is consistent with California Penal Code
> § 13663 as currently in effect, with any subsequent amendments or
> Attorney General guidance, and with the agency's own discipline,
> records-retention, and procurement policies. Bracketed placeholders
> in the form `[LIKE THIS]` are intended to be filled in by the
> adopting agency.

---

## 1. Purpose and authority

### 1.1 Purpose

This policy governs the use of artificial intelligence ("AI") in the
preparation of official reports and report-adjacent work product by
[AGENCY NAME] personnel. It establishes the agency's affirmative
obligation, under California Penal Code § 13663, to disclose AI use on
the face of every AI-assisted official report, to obtain a personal
attestation from the preparing officer, to retain the first AI draft,
to maintain an audit trail of every AI use, and to bind any AI vendor
contractually and operationally to the statutory carve-outs.

### 1.2 Authority

This policy is adopted under the authority of the Chief of Police of
[AGENCY NAME] pursuant to [LOCAL CHARTER / MUNICIPAL CODE CITE] and is
required by California Penal Code § 13663(a), which provides that
"Each law enforcement agency shall maintain a policy" governing the
matters set forth in that section. The statute became operative
January 1, 2026, and the obligations described below apply to every
official report prepared in whole or in part with AI on or after that
date.

### 1.3 Relationship to other policies

This policy supplements and does not displace:

1. [AGENCY NAME] Records Management Policy [NUMBER].
2. [AGENCY NAME] Body-Worn Camera / Digital Evidence Policy [NUMBER].
3. [AGENCY NAME] Information Security Policy [NUMBER].
4. The agency's CJIS Security Policy compliance obligations.
5. The California Public Records Act and the agency's discovery
   obligations under Penal Code § 1054.1.

Where this policy is more protective than another agency policy with
respect to AI use, this policy controls. Where this policy is silent
and another policy speaks, that policy controls.

### 1.4 Interpretation

This policy shall be interpreted in a manner consistent with the
statute. If the statute is amended, the amended statute controls
until this policy is re-issued. The City Attorney shall be consulted
on any interpretive question that materially affects compliance.

---

## 2. Scope

### 2.1 Reports covered

This policy applies to every "official report" prepared by, or on
behalf of, [AGENCY NAME] when AI is used, in whole or in part, to
generate, summarize, draft, translate, restructure, or enhance the
narrative or factual content of the report. "Official report" has
the meaning given in § 13663(e) — the final version of the report
that is signed by the officer.

Without limitation, the following are covered when AI is used in
their preparation:

1. Incident reports, supplemental reports, and crime reports.
2. Arrest reports and booking narratives.
3. Investigative case reports, including cold-case investigative
   summaries.
4. Use-of-force reports.
5. Traffic-collision narratives.
6. Probable-cause statements and search-warrant affidavit narratives
   where AI was used in their drafting (subject to Section 5.5
   prohibitions).
7. Any other report that, if produced manually, would be filed as an
   official agency report of record.

### 2.2 AI uses covered

This policy applies to any use of "artificial intelligence" as
defined in § 13663(e): a system that "infers from the input it
receives how to generate outputs." That definition is broad and is
read to include, without limitation:

1. Generative-AI drafting and summarization (e.g., Microsoft 365
   Copilot in the GCC tenant, hereafter "GCC Copilot").
2. AI-assisted summarization of body-worn-camera or interview-room
   audio or video.
3. AI-assisted timeline construction from records.
4. AI-assisted legal-element or CalCrim / Penal Code lookup that
   inserts text into a report draft.
5. AI-assisted interview-question generation that is later quoted in
   a report.
6. AI-assisted translation of witness or suspect statements where the
   translation is incorporated into the report.

### 2.3 Uses not covered

The following are **not** "AI use" for purposes of this policy,
unless their output is incorporated into the report narrative:

1. Spell-check and grammar-check tools that do not generate new
   substantive content.
2. Pre-existing rule-based form auto-population (drop-downs, code
   tables, deterministic field copy).
3. CAD/RMS field auto-population that is purely lookup-based.
4. Stand-alone records search where the officer reads results and
   types the report independently.

When in doubt, treat the use as covered and follow Section 6.

---

## 3. Authorized AI systems

### 3.1 Inventory

[AGENCY NAME] shall maintain an **AI Program Inventory** identifying
each AI system authorized for use in official-report preparation,
the version or model identifier of each system, the date authorized,
and the office or vendor responsible. The Inventory shall be reviewed
at least annually (Section 12) and updated upon any addition,
removal, or material change.

### 3.2 Default authorized system

The default authorized AI system is **Microsoft 365 Copilot operating
within [AGENCY NAME]'s Microsoft 365 Government Community Cloud
("GCC") tenant**, accessed through the agency's Cold Case governance
layer. Use of Copilot outside the agency's GCC tenant (for example,
commercial Microsoft 365 Copilot or personal accounts) is prohibited
for official-report preparation.

### 3.3 Vendor onboarding

No AI system may be added to the Inventory until:

1. The vendor's contract with the agency contains a data-handling
   clause consistent with § 13663(d) (see Section 9).
2. The City Attorney has reviewed and approved the contract clause.
3. The agency's Information Security Officer has reviewed the
   system's CJIS-alignment posture, where applicable.
4. The Chief of Police or designee has approved the addition in
   writing and recorded the approval in the Inventory.

### 3.4 Removal

An AI system shall be removed from the Inventory upon discovery of a
material compliance defect, expiration or termination of the
underlying contract, or written direction of the Chief of Police or
City Attorney. Removal must be announced to all authorized users and
must be enforced in the Cold Case authorization layer within one (1)
business day.

> **How Cold Case enforces this.** The AI Program Inventory is
> produced from production usage rather than from configured aliases —
> the model identifier captured on each first AI draft is the exact
> identifier returned by the provider (for example,
> `gpt-4o-mini-2024-07-18`). The annual attestation under Section 12
> is generated from this inventory. A model identifier that does not
> appear on the Inventory will appear on the Refusal & Anomaly Report
> and is subject to Section 11.

---

## 4. Authorized users

### 4.1 Eligibility

Only the following personnel may use an authorized AI system to
prepare an official report:

1. **Sworn personnel** of [AGENCY NAME] in active status.
2. Who have **completed initial AI-use training** as required by
   Section 10.
3. Whose AI use has been **approved by an immediate supervisor**
   (sergeant or above) and recorded in the agency's identity
   provider.
4. Whose authorization has **not been revoked** for any reason
   described in Section 4.4.

### 4.2 Non-sworn personnel

Non-sworn personnel (records clerks, civilian analysts, interns) may
not prepare or sign official reports using AI. Non-sworn personnel
may use AI for non-report work (e.g., administrative correspondence,
internal summaries) subject to [AGENCY NAME] Information Security
Policy [NUMBER] but outside the scope of this policy.

### 4.3 Supervisory approval

Supervisory approval shall be granted on a per-user basis, not on a
per-report basis. Approval is revocable at any time without cause.
Approval shall be reviewed annually as part of each user's
performance evaluation.

### 4.4 Revocation

Authorization to use AI under this policy is automatically revoked
upon:

1. Separation from [AGENCY NAME].
2. Placement on administrative leave related to misconduct.
3. Discipline for a violation of this policy (Section 11).
4. Lapse of required annual refresher training (Section 10.2).
5. Written direction of the Chief of Police, City Attorney, or the
   user's commanding officer.

> **How Cold Case enforces this.** Cold Case derives user identity
> from the agency's Entra ID / GCC identity provider. Removal of a
> user from the agency's AI-authorized group in the identity provider
> takes effect at the next Cold Case session and is recorded in the
> audit trail. The development-mode authentication bypass is
> prohibited in any production deployment of Cold Case under this
> policy.

---

## 5. Permitted and prohibited uses

### 5.1 Permitted uses

Subject to this policy, an authorized user may use an authorized AI
system to:

1. **Draft** narrative sections of an official report from materials
   the user has personally reviewed.
2. **Summarize** body-worn-camera, interview-room, or other audio or
   video the user has personally reviewed.
3. **Summarize** lengthy documentary evidence the user has personally
   reviewed.
4. **Build timelines** from records and media in the user's case
   file.
5. **Look up** CalCrim instructions, Penal Code sections, or other
   legal-element references for inclusion in the report.
6. **Generate interview questions** for the user's own preparation;
   any AI-generated question that is asked of a subject must be
   attributed in the report as having been asked by the officer.
7. **Translate** statements where the user lacks the language and the
   agency has authorized AI translation; the translation is the
   officer's work product upon adoption and the officer remains
   responsible for its accuracy.

### 5.2 Officer-as-author principle

The officer is at all times the author of the official report. AI
output is a draft offered to the officer; the officer must
independently verify every factual assertion against the underlying
evidence before adopting any AI output into a report.

### 5.3 Mandatory review

No AI output may be incorporated into an official report without the
officer's contemporaneous, line-by-line review against source
materials the officer has personally reviewed.

### 5.4 No batch sign-off

An officer shall not sign reports in batches without per-report
review. Each officer signature constitutes the attestation set forth
in Section 6.4 and § 13663(a)(2).

### 5.5 Expressly prohibited uses

AI shall **not** be used as the sole basis for, and an AI output
shall **not** be presented in any official report or proceeding as,
any of the following:

1. **Probable cause** for arrest, search, or seizure.
2. **Witness or suspect identification.**
3. **Any determination of guilt** or of any element of an offense.
4. **Risk scoring or predictive assessment** of an individual person
   for any law-enforcement decision (this is not a permitted use of
   AI under this policy; separate policy would be required).
5. **Generation of evidence** that did not exist in the case file
   before the AI was invoked (AI may summarize, restructure, or
   describe existing evidence; AI may not invent evidence).
6. **Mimicry of a person's voice or likeness** for any operational
   purpose.

An officer who is uncertain whether a contemplated use is prohibited
shall consult a supervisor before proceeding.

### 5.6 Hallucination risk

The officer is on notice that AI systems may generate text that
appears authoritative but is factually incorrect (commonly called
"hallucinations"). The officer's signature under Section 6.4 is the
officer's representation that the officer has detected and corrected
all such errors before signing.

> **How Cold Case enforces this.** Cold Case logs every prompt and
> response in the chain of custody and surfaces unusual AI behavior
> (refusals, off-scope output, prompt-injection patterns) on the
> Refusal & Anomaly Report (F17) for supervisory review. Cold Case
> does not, and cannot, detect every hallucination; the officer
> remains responsible under Section 5.2.

---

## 6. Required workflow for every AI-assisted report

### 6.1 Capture in the governance layer

All AI use covered by this policy shall be conducted through the
agency's Cold Case governance layer or another channel approved in
writing by the Chief of Police that produces an equivalent audit
trail. AI use through an unmanaged channel (personal device,
unmanaged browser session, personal account) is prohibited.

### 6.2 Verbatim disclosure on the report

Every AI-assisted official report shall bear, on its face, the
following statement, **quoted verbatim from § 13663(a)(1)**:

> "This report was written either fully or in part using artificial
> intelligence."

This statement shall appear on the first page of the report and
shall be repeated on every subsequent page in a position where a
reasonable reader will see it. The statement shall not be abbreviated,
paraphrased, hidden in a footnote, printed in a smaller typeface than
the body text, or removed by any post-export editing.

### 6.3 Identification of AI program

The report shall identify, by name and version or model identifier,
each AI program used in its preparation. Identification shall use
the program identifier as it appears in the AI Program Inventory
(Section 3.1). Where multiple AI programs were used, each shall be
named.

### 6.4 Officer signature and attestation

The report shall bear the **signature of the preparing officer** in
physical or electronic form. The signature constitutes the officer's
representation, **in the words of § 13663(a)(2)**, that the officer:

> "reviewed the contents of that report and that the facts contained
> in the official report are true and correct."

The signature shall be applied through the Cold Case governance
layer and shall be derived from the officer's authenticated session.
An officer shall not authorize another person to sign on the
officer's behalf and shall not share authentication credentials for
the purpose of signing.

### 6.5 Sequencing

The required sequence for any AI-assisted report is:

1. Officer initiates AI session within Cold Case.
2. Officer reviews and revises AI output.
3. Officer promotes a final draft to a Report record.
4. Officer signs the Report (Section 6.4).
5. Cold Case generates the export bearing the disclosure (Section
   6.2), AI program identification (Section 6.3), and signature
   block.
6. The signed export is filed in [RMS / case-management system].

No export may be filed before steps 1 through 5 are complete in
order.

### 6.6 First-draft preservation

The first AI draft shall be preserved as set forth in Section 7
below. The first AI draft is not the official report.

> **How Cold Case enforces this.** Cold Case stamps the verbatim
> disclosure on every page of the exported PDF, populates the AI
> program identification from the model identifier returned by the
> provider on the first draft, requires officer e-signature before
> permitting export (the export endpoint returns HTTP 422 referencing
> § 13663(a)(2) until the signature is captured), and writes each
> step in the sequence above to the tamper-evident audit chain. A
> request to export without a captured signature is refused and
> logged.

---

## 7. First-draft preservation

### 7.1 Definition

The "first draft" is, **in the words of § 13663(e)**, "the initial
document or narrative produced solely by artificial intelligence."
For purposes of this policy, the first draft is the AI output that
the officer first promotes toward the report — that is, the AI text
that becomes the starting point for the officer's review and
revision. Where the officer regenerates the AI output before
promoting, the promoted output is the first draft of the report;
regenerated alternatives are preserved as part of the audit trail
under Section 8 but are not the "first draft" for purposes of
§ 13663(b).

### 7.2 Retention period

The first draft shall be retained **for as long as the official
report is retained**, as required by § 13663(b). Where the official
report is retained for varying periods under the agency's
records-retention schedule, the longest applicable period controls
the first draft.

### 7.3 Non-statement

The first draft **shall not constitute an officer's statement.** It
shall not be released, produced, quoted, or treated as if it were
the officer's statement. Every release of the first draft (for
example, in discovery production under Penal Code § 1054.1) shall
be conspicuously labeled:

> "First AI draft — not an officer statement (§ 13663(b))."

### 7.4 No mutation

Once the first draft is captured, it shall not be edited, redacted
(except for lawful redaction at the time of release), reformatted,
or replaced. Any attempt to mutate a captured first draft is a
violation of this policy and shall be treated under Section 11.

### 7.5 Destruction

The first draft shall be destroyed only when the underlying official
report is destroyed under the agency's records-retention schedule,
and only after the City Attorney's office has confirmed that no
litigation hold or discovery obligation prevents destruction.

> **How Cold Case enforces this.** Cold Case marks the promoted AI
> message with `is_first_ai_draft=True` and locks it to the report.
> The retention sweeper excludes locked first drafts from purge so
> long as the report exists. Mutation attempts on a first-draft
> message are denied with an HTTP 403 and recorded as a
> `FIRST_DRAFT_MUTATION_BLOCKED` audit event. Releases of the first
> draft through the F4 audit export and the F8 discovery package
> carry the "not an officer statement" label automatically.

---

## 8. Audit trail

### 8.1 Logged events

[AGENCY NAME] shall maintain a complete, tamper-evident audit trail
of every AI use covered by this policy. The audit trail shall
identify, at a minimum, for each AI use:

1. **The person who used AI**, by authenticated user identifier and
   display name (§ 13663(c)(1)).
2. **The AI program**, by name and model identifier as returned by
   the provider.
3. **The timestamp** of each prompt, response, regeneration, promote,
   edit, and signature event.
4. **The source materials** referenced by the user in the AI session,
   including documents and **video and audio footage** used to create
   the report, by stable identifier or hash (§ 13663(c)(2)).
5. **The full prompt-and-response chain** that produced the first
   draft, including regenerated alternatives.
6. **Officer review actions** between first draft and signature.
7. **The signature event**, including content hash, signer identifier,
   timestamp, and intent-to-sign attestation.
8. **Vendor access events**, where applicable (Section 9).

### 8.2 Tamper-evidence

The audit trail shall be maintained in a form that allows after-the-
fact verification that no entry has been altered. Hash-chaining of
audit events (each event references the cryptographic hash of the
prior event) satisfies this requirement.

### 8.3 Retention

Audit entries for an AI-assisted report shall be retained for at
least as long as the official report and the first draft are
retained.

### 8.4 Access

Access to the audit trail shall be limited to:

1. The **City Attorney** of [JURISDICTION] and authorized staff.
2. The **agency auditor** or other internal-affairs personnel
   designated by the Chief of Police.
3. **Court personnel** acting under a lawful court order.
4. **District-attorney personnel** acting in discharge of statutory
   discovery duties.
5. Other persons identified in a written records-access policy
   approved by the Chief of Police and City Attorney.

Access shall itself be logged.

### 8.5 Production format

The audit trail shall be producible as a signed, self-verifying
chain-of-custody document suitable for filing as an exhibit. The
production format shall be the format approved in [AGENCY NAME]'s
discovery protocol.

> **How Cold Case enforces this.** Cold Case writes an audit event
> for each action enumerated in Section 8.1 and chains each event by
> the hash of the prior event. The chain-of-custody PDF (F7) prints
> the complete chain with timestamps, actor identifiers, the media
> inventory referenced in any prompt, and the running hash on the
> final page so that a city attorney can re-verify the chain months
> after the fact. Access to the audit trail is itself logged.

---

## 9. Vendor restrictions

### 9.1 Contractual obligation

Every agreement under which a vendor provides an AI service used in
official-report preparation shall include a data-handling clause
that, at a minimum, **restates § 13663(d) verbatim** and binds the
vendor to its terms. **In the words of § 13663(d)**, the vendor

> "shall not share, sell, or otherwise use the information provided
> by the agency"

except:

1. To **provide the contracted service** to that agency.
2. To **comply with a court order**.
3. For **troubleshooting, bias mitigation, accuracy improvement, or
   system refinement.**

### 9.2 Reference clause

The agency's model vendor data-handling clause is maintained at
[`vendor-data-handling-clause.md`](./vendor-data-handling-clause.md)
and shall be the starting point for every AI-vendor procurement.
Departures from the model clause shall be approved by the City
Attorney in writing.

### 9.3 Access-request workflow

Where a vendor seeks access to agency data for any of the carve-out
purposes in Section 9.1, the vendor shall submit an access request
that identifies:

1. The **purpose** of the access, by reference to one of the (d)
   carve-outs.
2. The **scope** of the access, by case identifier, report
   identifier, or other narrowest-practicable identifier.
3. The **time window** of the access.
4. The **vendor personnel** who will perform the access.

The request shall be approved in writing by the Chief of Police or
designee before the access is enabled and shall be reviewed by the
agency auditor under Section 12.

### 9.4 Scope enforcement

Vendor access shall be limited, at the software layer, to the scope
identified in the approved access request. Off-scope access attempts
shall be refused and logged.

### 9.5 Periodic review

The agency auditor shall review every vendor access event on at
least a monthly cadence. Patterns of repeated access, scope
expansion, or anomalous activity shall be reported to the Chief of
Police and the City Attorney.

> **How Cold Case enforces this.** Cold Case represents each
> approved vendor access as a `VendorAccessRequest` with explicit
> purpose, scope, and time window. The `vendor_scope` service
> refuses off-scope requests at the request layer, returning HTTP
> 403 and a `VENDOR_ACCESS_SCOPE_VIOLATION` audit event. Vendor
> access events appear on the Refusal & Anomaly Report (F17) for
> the auditor's monthly review under Section 9.5.

---

## 10. Training

### 10.1 Initial training

No person shall use AI to prepare an official report until that
person has completed [AGENCY NAME]'s initial AI-use training. The
training shall cover, at a minimum:

1. The text of Penal Code § 13663 and the obligations of the agency
   under the statute.
2. The text of this policy, with emphasis on Sections 5 (permitted
   and prohibited uses), 6 (required workflow), and 7 (first-draft
   preservation).
3. Practical use of the authorized AI system(s) through Cold Case,
   including the signature workflow and the disclosure language.
4. The officer's accountability under Section 5.2 (officer as
   author) and the risk of AI hallucination under Section 5.6.
5. The audit trail and the officer's expectation that every prompt
   and response is logged.
6. Examples of prohibited uses (Section 5.5), including realistic
   scenarios.

### 10.2 Annual refresher

Every authorized user shall complete an annual refresher covering
any statutory or policy changes since the prior training and a
review of any recurring policy violations identified in the prior
year's annual review (Section 12). Failure to complete the annual
refresher results in automatic revocation of authorization under
Section 4.4(4).

### 10.3 Records

The agency shall retain training records for each authorized user
for at least five (5) years after the user's separation or
revocation of authorization.

### 10.4 New-system training

The addition of a new AI system to the Inventory triggers a
mandatory supplemental training module before any authorized user
may use the new system on an official report.

---

## 11. Violations

### 11.1 Examples of violations

Conduct constituting a violation of this policy includes, without
limitation:

1. Using an AI system that is not on the AI Program Inventory.
2. Using a personal account, personal device, or non-agency channel
   for AI-assisted report preparation.
3. Signing an official report without contemporaneous, line-by-line
   review (Section 5.3) or in batches (Section 5.4).
4. Attempting to mutate, delete, replace, or suppress a captured
   first AI draft (Section 7.4).
5. Removing, abbreviating, paraphrasing, or hiding the verbatim
   disclosure required by Section 6.2.
6. Omitting the AI program identification required by Section 6.3.
7. Using AI for any expressly prohibited purpose under Section 5.5.
8. Sharing authentication credentials for the purpose of having
   another person sign a report (Section 6.4).
9. Disabling, circumventing, or attempting to circumvent any audit-
   trail mechanism.
10. Failing to complete required training (Section 10).
11. Approving a vendor access request without an applicable § 13663(d)
    carve-out, or enabling vendor access without an approved request
    (Section 9.3).

### 11.2 Discipline

A violation of this policy is grounds for discipline under [AGENCY
NAME] Personnel Rules [CITE], up to and including termination, and
may also constitute grounds for prosecutorial notification under
Brady / Giglio obligations. Discipline shall be administered in
accordance with the agency's existing disciplinary process and any
applicable collective-bargaining agreement.

### 11.3 Reporting

Any [AGENCY NAME] personnel with knowledge of a suspected violation
shall report the suspected violation to the user's immediate
supervisor or, where the supervisor is implicated, to the
supervisor's commander or to internal affairs.

### 11.4 Non-retaliation

[AGENCY NAME] prohibits retaliation against any person who in good
faith reports a suspected violation of this policy.

### 11.5 Tolling for litigation hold

Where a suspected violation may bear on a pending criminal or civil
proceeding, no records concerning the AI use in question shall be
destroyed pending resolution, regardless of the otherwise-applicable
retention schedule.

---

## 12. Annual review and attestation

### 12.1 Annual review

The Chief of Police, in consultation with the City Attorney, shall
review this policy at least once per calendar year and revise it as
necessary to reflect:

1. Any amendment to Penal Code § 13663 or related statutes.
2. Any binding judicial decision or Attorney General opinion.
3. Any change in the AI Program Inventory or authorized vendors.
4. Recurring violations identified in the prior year and any
   corrective action taken.

### 12.2 Annual attestation

Following each annual review, the Chief of Police shall sign an
attestation that:

1. This policy has been reviewed.
2. The AI Program Inventory has been refreshed against actual
   production usage.
3. The audit trail has been spot-checked and verified by the agency
   auditor.
4. All authorized users have current refresher training on file.
5. All AI-vendor contracts contain the § 13663(d) clause.

The attestation shall be filed with the City Clerk and made available
to the City Council on request.

### 12.3 Spot-check

As part of each annual review, the agency auditor shall pull at
random no fewer than five (5) closed AI-assisted reports and verify
that:

1. Each retained first draft is readable and matches the snapshot
   hash recorded on the report.
2. The audit chain for each report verifies end-to-end.
3. Each export carries the verbatim disclosure and the correct AI
   program identifier on every page.
4. Each export bears a captured officer signature.

Findings shall be appended to the annual attestation.

### 12.4 Public reporting

[AGENCY NAME] may, in the discretion of the Chief of Police and
subject to City Attorney review, publish a redacted summary of the
annual attestation. Publication is not required by this policy or
by the statute.

> **How Cold Case enforces this.** Cold Case produces the AI Program
> Inventory and the annual-attestation evidence pack from production
> data on demand. The chain-of-custody verification for the annual
> spot-check is run from the audit chain rather than reconstructed by
> hand.

---

## 13. Definitions

The following definitions apply throughout this policy. Definitions
1 through 4 **mirror § 13663(e)** and shall be read consistently with
that subdivision.

1. **"Artificial intelligence"** or **"AI"** — a system that infers
   from the input it receives how to generate outputs (mirroring
   § 13663(e)). The term includes both AI used to draft a narrative
   from camera footage and generative AI used to enhance an officer's
   draft.

2. **"Official report"** — the final version of the report that is
   signed by the officer (mirroring § 13663(e)).

3. **"First draft"** — the initial document or narrative produced
   solely by artificial intelligence (mirroring § 13663(e)).

4. **"Used in part"** — AI was used at any stage of the preparation
   of the report, even if the officer subsequently rewrote a
   substantial portion of the AI output. If AI was used, the report
   is AI-assisted for purposes of this policy.

5. **"Authorized user"** — a person meeting the requirements of
   Section 4.1.

6. **"Authorized AI system"** — an AI system listed in the current
   AI Program Inventory under Section 3.1.

7. **"Cold Case"** — [AGENCY NAME]'s AI-governance layer of record
   for AI-assisted report preparation, including its audit, signature,
   export, and vendor-scope-enforcement components.

8. **"GCC Copilot"** — Microsoft 365 Copilot operating within
   [AGENCY NAME]'s Microsoft 365 Government Community Cloud tenant.

9. **"Vendor"** — a person or entity, other than [AGENCY NAME] and
   its personnel, that provides an AI service used in official-report
   preparation under contract with the agency.

10. **"Vendor access"** — any access by vendor personnel to data
    that the agency provided to the vendor in connection with the
    AI service.

11. **"Audit trail"** — the tamper-evident record of AI use
    described in Section 8.

12. **"City Attorney"** — the City Attorney of [JURISDICTION] and
    authorized staff.

13. **"Agency auditor"** — the person or office designated by the
    Chief of Police under Section 8.4(2).

14. **"AI Program Inventory"** — the list maintained under Section
    3.1.

15. **"Refusal & Anomaly Report"** — the recurring report described
    in Cold Case feature F17, surfacing AI refusals, vendor access
    events, and anomalous use patterns for supervisory review.

---

## 14. Adoption

This policy is adopted by [AGENCY NAME] effective on the date
written below.

| Role | Name | Signature | Date |
|---|---|---|---|
| Chief of Police, [AGENCY NAME] | [NAME] | __________________________ | __________ |
| City Attorney, [JURISDICTION] | [NAME] | __________________________ | __________ |
| Records Custodian | [NAME] | __________________________ | __________ |

**Effective date:** [EFFECTIVE DATE — on or after 2026-01-01]

**Next scheduled review:** [EFFECTIVE DATE + 1 YEAR]

---

## Appendix A — Disclosure block (copy-paste form)

The following is the canonical disclosure block to be printed on
every page of every AI-assisted official report. The first line is
**verbatim § 13663(a)(1)** and shall not be altered.

```
This report was written either fully or in part using artificial
intelligence.

AI program(s) used: [PROGRAM NAME], [VERSION OR MODEL IDENTIFIER]
Prepared by:       [OFFICER NAME], [BADGE/ID]
Signed:            [TIMESTAMP, TIMEZONE]   Signature ID: [SIG ID]
Report ID:         [REPORT ID]              Case ID: [CASE ID]
```

## Appendix B — Officer attestation block (copy-paste form)

The following is the canonical attestation block applied at signing.
The quoted line is **verbatim § 13663(a)(2)**.

```
I, [OFFICER NAME], [BADGE/ID], have reviewed the contents of this
report and the facts contained in this official report are true and
correct.

Signed (electronic):  [SIGNATURE HASH]
Timestamp:            [ISO-8601 TIMESTAMP, TIMEZONE]
Content SHA-256:      [HASH]
Authentication:       [IDP SUBJECT / SESSION ID]
```

## Appendix C — Cross-reference to § 13663

| Policy section | Statute |
|---|---|
| §§ 1, 2, 3, 4 | § 13663(a) chapeau (agency-policy requirement) |
| § 6.2, 6.3, Appendix A | § 13663(a)(1) (disclosure + AI program identification) |
| § 6.4, Appendix B | § 13663(a)(2) (officer signature and attestation) |
| § 7 | § 13663(b) (first-draft retention; non-statement) |
| § 8 | § 13663(c) (audit trail: person + media) |
| § 9 | § 13663(d) (vendor restrictions and carve-outs) |
| § 13 | § 13663(e) (definitions) |

---

*End of policy.*
