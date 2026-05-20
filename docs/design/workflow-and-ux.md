# Workflow & UX — Cold Case

**Status:** Draft for review · **Author:** Cold Case eng · **Date:** 2026-05-20
**Audience:** Dan + the detective sponsor. Not a spec yet — this is the *frame* before we cut into the UI.

> Today the product is a **chat-with-case + statute-grade audit trail** wrapped in a 3-pane layout. That gets the compliance story across, but it doesn't yet *feel like* the place a detective works. This doc walks the detective's day, names every artifact that gets created, and proposes the IA, screens, and visual language to make the workflow land.

---

## 1. Who is the user, and what is their day?

Detective Gaudi's day, mapped to Cold Case:

```
  cold case lands on desk
        │
        ▼
  (a) gather what exists  ── patrol PDFs, witness statements, photos, audio xfer
        │
        ▼
  (b) read & orient       ── skim everything, mental model: who/what/when/where
        │
        ▼
  (c) ask the case        ── "summarize the patrol report", "build a timeline for the DA"
        │                     "what gaps are in my report vs CalCrim 540A?"
        ▼
  (d) write the report    ── start from AI draft, edit, cite, attest
        │
        ▼
  (e) sign & ship         ── e-sign, export PDF, upload to evidence.com, hand to DA
        │
        ▼
  (f) defend the work     ── 6 months later, DA / defense / city attorney asks
                             "show me the prompt chain" → discovery export
```

**The detective only spends ~10% of their time on (e) and (f).** The product needs to feel like it's *built for* (b)–(d), with (e)–(f) being one button each.

---

## 2. Current state — honest assessment

What's built (from reading the code, not the marketing):

| Surface | What it is today | What it does well | What hurts |
|---|---|---|---|
| `/` Dashboard | not yet built | — | no anchor for "what's mine, what's stale, what needs my signature" |
| `/cases` Case list | table of cases + "New case" modal + seed buttons | classification badges, homicide indefinite-retention hint, fast | flat table — no filter beyond status, no tags, no "my cases", no aging signal |
| `/cases/:id` Case detail | **3-pane**: docs sidebar / doc viewer / chat panel. Compliance accordion at the bottom. | citations chip-jump from chat to doc + line is excellent; auto-conversation is a nice touch | the page tries to be the *whole* case workspace in one view. Reports are hidden inside a drawer; timeline, people, media all share one sidebar; discovery export is buried |
| `ReportDrawer` | 989-line drawer doing promote/edit/revise/sign/export/chain | reviewable in-place | size + drawer-shape forces a modal-y interaction over what should be a first-class workspace |
| `/audit` | filterable event table | exists, statute-aligned event types | global only — no per-case scoped audit view in the case context |
| `/admin` | Launchpad Admin pattern | RBAC works | not the detective's concern; correctly out of the way |

**What's missing entirely:**
- A **dashboard** anchored to *me as the detective* (my cases, my drafts, my unsigned reports, alerts).
- **Tags** of any kind (only `classification` exists on the case record).
- A **timeline** view of the case (a top-3 detective use-case in the interview).
- A **people / entities** view (suspects, witnesses, victims) — a Copilot output today; not a first-class noun in our model.
- A **case-state hero**: at a glance, where is this case in its lifecycle?
- Real **evidence.com handoff** (501 today).
- A **briefing surface** — the one-page "case brief" a sergeant or city attorney reads before approving an action.

---

## 3. The artifact lifecycle (what gets *created*, end to end)

This is the picture the UI should make obvious. Every box is something the user creates, sees, tags, or exports. Every arrow is an action.

```
    [Source documents]        [Media inputs]           [Manual entities]
       (PDF, scan,              (audio, video           (suspects,
        statement)               transcript)             witnesses,
           │                          │                   victims)
           │ register/upload          │ register          │ add
           ▼                          ▼                   ▼
    ╔═══════════════════════════════════════════════════════════╗
    ║                       CASE WORKSPACE                       ║
    ║   (everything below lives inside one case, scoped, tagged) ║
    ╠═══════════════════════════════════════════════════════════╣
    ║                                                           ║
    ║   Conversation  ───►  Assistant message  (with citations) ║
    ║   (chat thread)                  │                        ║
    ║                                  │ promote                ║
    ║                                  ▼                        ║
    ║                          Report draft                     ║
    ║                          (= first AI draft, immutable)    ║
    ║                                  │                        ║
    ║                                  │ edit, revise, cite     ║
    ║                                  ▼                        ║
    ║                          Signed report                    ║
    ║                          (= official report)              ║
    ║                                                           ║
    ╠═══════════════════════════════════════════════════════════╣
    ║                                                           ║
    ║      Audit trail   (every prompt, every response,         ║
    ║                     every promote/edit/sign event)        ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
       Report PDF       Chain-of-custody    Discovery ZIP
       (+ disclosure)   PDF (full chain)    (signed reports +
                                             chains + manifest)
            │                                  │
            ▼                                  ▼
     evidence.com                       DA / defense / city attorney
     (per-report)                       (per case)
```

**Every artifact already exists in the backend.** What's missing is the UI surface that lets the detective *navigate them as a set*, not hunt for them.

---

## 4. Proposed information architecture

### 4.1 Global navigation (left rail)

```
   ▌Dashboard                ← me-centric: my cases, my drafts, alerts
   ▌Cases                    ← all cases I can see
   ▌Audit                    ← global events (city attorney's home)
   ▌Admin                    ← RBAC, retention, compliance preflight
   ─────────
   ▌Templates  (Phase 2)     ← prompt + report templates (the Copilot "notebook" feel)
```

### 4.2 The case workspace (the core screen)

Instead of one 3-pane view that tries to do everything, **make the case a tabbed workspace** with the chat persistent on the right (because chat is the verb of the product).

```
   ┌─────────────────────────────────────────────────────────────────────┐
   │  ◄ Cases   CC-2026-0001 · 1987 Riverside Park homicide              │
   │  ──────────────────────────────────────────────────────────────────  │
   │  ▌HOMICIDE  ▌OPEN  ▌ASSIGNED TO ME  ▌RETENTION: INDEFINITE          │
   │  ▌3 docs · 2 media · 1 signed report · last activity 2h ago         │
   │  [Tags:  #suspect:doe  #alibi  #forensics  +]                        │
   │  ──────────────────────────────────────────────────────────────────  │
   │ ┌─────────────────────────────────────┐ ┌─────────────────────────┐ │
   │ │  Brief  │ Evidence │ Timeline │ Peop│ │   💬  Conversation       │ │
   │ │  le │ Reports │ Chain │ Export      │ │                         │ │
   │ │ ─────────────────────────────────── │ │  …chat messages…        │ │
   │ │                                     │ │                         │ │
   │ │       (tab content here)            │ │  [↳ promote to report]  │ │
   │ │                                     │ │                         │ │
   │ │                                     │ │ ┌───────────────────────┐│ │
   │ │                                     │ │ │ Ask the case…         ││ │
   │ │                                     │ │ │ [📎docs] [🎙media] →  ││ │
   │ │                                     │ │ └───────────────────────┘│ │
   │ └─────────────────────────────────────┘ └─────────────────────────┘ │
   └─────────────────────────────────────────────────────────────────────┘
```

**The tabs:**

| Tab | What lives here | Replaces today's… |
|---|---|---|
| **Brief** | One-page overview: classification, status, retention clock, key dates, primary investigator, suspects/victims at a glance, last activity, "what's needed next" cues | dashboard view of a single case (none today) |
| **Evidence** | Documents + media. Grouped by *type* (reports, photos, witness statements, forensics) with tag filters. Per-item extraction status, hash, source URI. | today's flat docs sidebar |
| **Timeline** | Chronological view of events drawn from documents (AI-extracted) + chat conversations + report events. Filterable by date range, by person. | nothing today (key gap) |
| **People** | Entities: suspects / witnesses / victims / officers of record. Manually-added with AI-suggested. Each links to the docs/messages where they appear. | nothing today (key gap) |
| **Reports** | List of all reports for this case: drafts, signed, exported. Each opens the report workspace (current ReportDrawer, but as a full page, not a drawer). | report drawer (promoted to full surface) |
| **Chain of custody** | Per-case audit timeline. Same data as global `/audit` but scoped + visualized as a chain. Download chain.pdf or audit-manifest.pdf. | today's bottom-of-page compliance accordion |
| **Export** | Discovery ZIP, evidence.com publish, public-records redacted bundle. Records-officer surface. | today's bottom-of-page compliance accordion |

**The chat panel never moves.** It's the verb — always available, always scoped to the case, citations always click-jump to the right document in the Evidence tab.

### 4.3 The dashboard (new — `/`)

```
   ┌─────────────────────────────────────────────────────────────────────┐
   │  Welcome, Det. Gaudi · Hopkinsville PD                              │
   │  ──────────────────────────────────────────────────────────────────  │
   │  ┌───────────────────────┐ ┌───────────────────────┐                │
   │  │  ▌Needs your action   │ │  ▌Recent activity     │                │
   │  │  • 2 reports unsigned │ │  • CC-...-0001 signed │                │
   │  │  • 1 first draft     │ │  • CC-...-0007 new doc│                │
   │  │    flagged for review │ │                       │                │
   │  └───────────────────────┘ └───────────────────────┘                │
   │  ┌─────────────────────────────────────────────────┐                │
   │  │  ▌My cases (8)                                  │                │
   │  │  CC-2026-0001  Riverside Park homicide   2h ago │                │
   │  │  CC-2026-0007  Smith burglary           1d ago  │                │
   │  │  ...                                            │                │
   │  └─────────────────────────────────────────────────┘                │
   │  ┌─────────────────────────────────────────────────┐                │
   │  │  ▌Agency alerts (city attorney / supervisor)    │                │
   │  │  • Anomaly: 3 refusal events on CC-...-0007    │                │
   │  │  • Vendor access requested by Cold Case eng     │                │
   │  └─────────────────────────────────────────────────┘                │
   └─────────────────────────────────────────────────────────────────────┘
```

Same dashboard, **role-aware**: detective sees their cases; sergeant sees team queue; city attorney sees the anomaly report and pending vendor access requests.

---

## 5. The tagging system (new — Phase 1)

§13663 doesn't require tags. The detective workflow does — Copilot notebooks have folders today, this needs an equivalent.

**Two kinds of tag:**

| Kind | Source | Examples | Mutable by user? |
|---|---|---|---|
| **System tag** | Server-applied based on state | `has-ai-draft`, `signed-report-present`, `ocr-only`, `discovery-exported`, `vendor-accessed`, `refusal-flagged` | No |
| **User tag** | User-applied freeform + agency-curated suggestions | `#suspect:doe`, `#alibi`, `#forensics`, `#witness:jane`, `#brady-relevant`, `#follow-up` | Yes |

**Where tags appear:**
- **Case** — top of the case page header. Filterable from case list.
- **Document** — under the doc title in the Evidence tab.
- **Message** — small chip at the bottom-right of each assistant message; useful for marking "this is the answer I'll use", "this is exculpatory", etc.
- **Report** — header of the Reports tab + on the signed PDF metadata (not on the page footer — would clutter).

**Data model (proposed):**
```
Tag { id, tenant_id, label, kind: system|user, color, created_by, created_at }
TagAssignment { id, tenant_id, tag_id, subject_kind: case|doc|msg|report, subject_id, applied_by, applied_at }
```

Tag-suggestion endpoint (Phase 2): given a case, the LLM proposes 5 candidate tags from the doc text. User accepts/rejects. This is cheap, high-value, and bounded — but defer until the core tag UX lands.

---

## 6. Artifact creation flows

### 6.1 From document → AI artifact

```
Evidence tab           Chat panel              Promote
┌─────────────┐       ┌─────────────┐         ┌────────────┐
│ [pdf] [pdf] │       │ Q: summarize│         │ Report     │
│ [pdf] [aud] │  ───► │ A: Per the…│  ───►   │ workspace  │
│             │       │   [📌 use   │         │ (full page,│
│             │       │    as draft]│         │  not draw) │
└─────────────┘       └─────────────┘         └────────────┘
```

A doc isn't "promoted" — a *message* about a doc is promoted. Today: works. The UI fix is making this a **full-page report workspace**, not a drawer slide-in; the report is a *first-class artifact* and deserves a route (`/cases/:id/reports/:rid`).

### 6.2 From AI artifact → official record

The report workspace, three columns:

```
┌──────────────────────────────────────────────────────────────────────┐
│  Report · Draft #2 · Case CC-2026-0001                               │
│  ────────────────────────────────────────────────────────────────────  │
│ ┌────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐ │
│ │ First AI draft │ │  Editor (final text) │ │  Citations / sources │ │
│ │ (immutable     │ │                       │ │                      │ │
│ │  §13663(b))    │ │  [editable body…]    │ │  [src: patrol.pdf,   │ │
│ │                │ │                       │ │   L42]  ← clickable  │ │
│ │  …text…        │ │  AI-revise          │ │                      │ │
│ │                │ │  ┌─────────────────┐ │ │  All citations valid │ │
│ │  [diff vs     │ │  │ instruction…    │ │ │  ✓ 12/12             │ │
│ │   current]    │ │  │             ↻  │ │ │                      │ │
│ └────────────────┘ │  └─────────────────┘ │ └──────────────────────┘ │
│                    │  ──────────────────  │                          │
│                    │  Sign & export       │                          │
│                    │  Officer: [name]    │                          │
│                    │  Badge:   [____]    │                          │
│                    │  [Attest + sign]    │                          │
│                    └──────────────────────┘                          │
└──────────────────────────────────────────────────────────────────────┘
```

The **revision timeline** (currently in the drawer) becomes a collapsible sidebar so it's available but not in the way.

### 6.3 Signed → exported → handed off

Three handoff paths, one button each in the **Export** tab:

| Target | What ships | Status today |
|---|---|---|
| **Local file** | Signed report PDF + chain-of-custody PDF | ✅ works |
| **evidence.com** | Same PDFs + push to evidence.com asset, returns asset URL, audit-logged | ❌ 501 stub |
| **Discovery ZIP** | All signed reports + chains + manifest + (optional) source binaries | ✅ works |
| **Public records redacted bundle** | Redacted PDF + redaction log + chain | ❌ not built |

Each handoff produces an **audit event** with destination + recipient + reason; the Export tab shows past handoffs for this case (so the records officer can answer "did we already send this to defense?" in one glance).

---

## 7. evidence.com integration (real, not stub)

**The shape (proposal):**

```
  Cold Case  ──POST /v2/api/agency-imports──►  evidence.com (per-agency tenant)
              + multipart:
                  - report.pdf
                  - chain.pdf  (as attachment / related file)
                  - manifest.json  (case_number, officer, hash, ai_programs[])
              ──204─►   Cold Case stamps Report.evidence_com_asset_id +
                       writes EVIDENCE_COM_PUBLISHED audit event
```

**Auth:** OAuth2 client-creds per agency. Stored as a `Provider` config in the existing provider seam (sibling to LLM provider). Token cached, refreshed on 401.

**Failure mode:** if evidence.com rejects (auth, quota, schema), surface the error inline in the Export tab with a "retry" button and a "download instead" fallback so the detective is never blocked.

**Why this matters now:** the entire pitch is "removes the manual PDF-and-upload step." Without evidence.com integration, the value prop is unproven. This should be Phase A.

---

## 8. Visual language

Cold Case is **gov + legal + 24h work**. Pick a palette that signals seriousness, makes status legible at a glance, and doesn't fatigue at 11pm.

**Principles:**
1. **Restrained chroma.** No playful colors. Slate base, blue primary, semantic accents (success/warning/danger) only used for *state*, never decoration. The current `index.css` token set is already close.
2. **Status is colored; chrome isn't.** A status badge can be red; a button border cannot. This forces color into meaning.
3. **Dense but breathable.** Detectives want to see a lot at once (it's a Bloomberg-terminal kind of job), but the page can't feel like an Excel grid. Achieved with strong section dividers, small but readable type (14px body), and consistent vertical rhythm.
4. **Statute citations always render the same way.** `§13663(b)` is *always* in the same monospace tag style. The reader's eye learns it.
5. **Citations are first-class chips.** Today's `[src: file.pdf, L42]` chip pattern is great — keep it, make it the model for tags, statute refs, and people-mentions.

**Specifically proposed token additions to `src/index.css`:**

```css
:root {
  /* Case-state palette — semantic, used only for state badges */
  --color-state-open: #2563eb;        /* blue   — active investigation */
  --color-state-active: #16a34a;      /* green  — fresh activity */
  --color-state-closed: #64748b;      /* slate  — archive */
  --color-state-reopened: #d97706;    /* amber  — attention */
  --color-state-discovery: #7c3aed;   /* purple — under discovery */

  /* Statute / legal anchor */
  --color-statute-fg: #0f172a;
  --color-statute-bg: #f1f5f9;
  --font-mono-tag: ui-monospace, "SFMono-Regular", Menlo, monospace;
}
```

**Iconography:** keep the current outline-style nav icons; add a small set of *artifact* icons (document, audio, image, signed-report, chain) used consistently. No emoji in the artifact set — too informal for legal context.

---

## 9. Phased plan

I want to keep this concrete enough that we can ticket it tomorrow.

### Phase A — "the workspace lands" (1 sprint, ~5 PRs)

Goal: a detective opens the case and immediately knows where they are.

1. **Tabbed case workspace** — convert `CaseDetailPage` into a tabbed shell. Brief / Evidence / Reports / Chain / Export tabs. Chat panel persistent on the right.
2. **Case-state hero band** — classification + status + retention + last-activity, immediately under the title.
3. **Promote Reports out of the drawer** — give reports their own route (`/cases/:id/reports/:rid`) and a 3-column workspace.
4. **Dashboard (`/`)** — me-centric landing. "My cases", "Needs my action", "Recent activity". Reuses existing list endpoints; minimal new backend.
5. **Surface compliance preflight** in the admin panel — display the JSON from `/admin/compliance/preflight` as a green/red checklist.

Backend touches: tiny (a `?mine=true` filter on `/cases`, a per-case "last_activity" derived field). No new entities.

### Phase B — "the case has a shape" (1–2 sprints)

Goal: the case has a brief and a timeline; tags exist; evidence.com is real.

6. **Tags MVP** — `Tag` + `TagAssignment` models, user tags first (no AI suggestions yet). Filter case list + Evidence tab by tag. System tags auto-applied on state transitions.
7. **Case brief tab** — assembled view from existing fields + manually-entered key dates and subject summary. No AI yet.
8. **Timeline tab** — chronological list of: report-signed, doc-registered, chat-promoted events, plus user-added timeline entries. Phase B does not auto-extract events from doc text — that's Phase C.
9. **evidence.com provider** — real integration behind the existing provider seam. Adds `EVIDENCE_COM_PUBLISHED` audit event and `Report.evidence_com_asset_id` field.
10. **Per-case chain-of-custody view** — same data as global audit, scoped + rendered as a vertical chain visualization. Download chain.pdf is the existing endpoint.

Backend touches: new `Tag` / `TagAssignment` models, evidence.com provider impl, optional `Report.evidence_com_asset_id`.

### Phase C — "the case is intelligent" (2+ sprints, stretch)

Goal: the case knows things about itself.

11. **People / entities tab** — AI-suggested entity extraction with detective accept/reject. `Person` model + `PersonMention` linking to docs/messages.
12. **AI-suggested tags** — given a case's docs, propose 5 tags. One-click accept.
13. **Timeline auto-extraction** — AI extracts dated events from doc text → proposed timeline entries → detective curates.
14. **Cross-case search** — full-text + tag-filter across all cases the user can see.
15. **Saved views / queries** — sergeant: "all open homicides assigned to my team with no activity in 14 days".

Backend touches: real ML/LLM work (entity extraction, timeline extraction). Belongs after Phase A + B prove the surface area.

---

## 10. What I'd *not* build (yet, on purpose)

- **A graph view of relationships across the case** (the "interesting" stretch from the call). High build cost, unproven need until the timeline and people tabs are in production and we see what people actually click.
- **Real-time collaboration** (multiple detectives in the same case). Not a confirmed need; adds a lot of plumbing.
- **A separate "supervisor" UI.** The dashboard becoming role-aware is the right move; a parallel UI is overkill.
- **Mobile.** Cold case work is desk-bound. A responsive table fallback for the case list is fine; a phone-first design isn't.

---

## 11. Design decisions (locked 2026-05-20)

User approved the IA + phased plan. The five open questions are resolved as follows:

1. **Reports** stay **inside the case workspace** as a tab. A "Pending signatures" card on the dashboard exposes the sergeant cross-case view without a parallel top-level route.
2. **Tag governance:** **closed agency vocabulary** for tags (legally durable, filter-stable) + a separate **free-form `Note` artifact** for detective workflow shorthand. Closed vocabulary aligns with evidence.com's category model — see §13.
3. **People tab** in Phase B: **manually entered**. AI-suggested entity extraction deferred to Phase C.
4. **evidence.com integration: deferred entirely.** Cold Case will *not* implement auth, push, or asset reconciliation in this batch. **However:** every artifact ships with the metadata + identifiers a future integration will need, so when the integration lands, no schema migration or backfill is required. See §13.
5. **Chain of custody tab** named **"Chain"** in the case workspace. The global page stays **"Audit"**.

---

## 13. Data readiness for future evidence.com export

> **Principle:** when evidence.com integration lands, it should be a *push job*, not a schema migration. Every field evidence.com asks for must already exist on the relevant artifact at create-time. This appendix locks that data plan.

### 13.1 What evidence.com expects (per their public schemas + agency import patterns)

For a future "publish signed report to evidence.com" call, the destination system will want roughly:

| Evidence.com field | Source on our side | Notes |
|---|---|---|
| `agency_ori` | Agency ORI | Identifies the agency in the federated platform. Snapshot at artifact creation (don't read live env at push time — agencies can move). |
| `case_number` | `Case.case_number` | Human-readable agency case identifier. |
| `external_id` | `Case.external_id` (new) | Stable dedupe key. Default value: `{ori}:{case_number}`. Required for idempotent push + future updates. |
| `incident_date` | `Case.date_of_incident` (new) | Distinct from `created_at`. The date of the underlying incident, not the date we registered it. |
| `incident_classification` | `Case.classification` | Maps to evidence.com category taxonomy. Mapping table lives in the future provider (`providers/evidence_com.py`). |
| `title` | `Case.title` | Verbatim. |
| `description` | `Case.description` | Verbatim. |
| `tags` / `categories` | `Tag` rows linked to case (Phase B) | Closed agency vocabulary, see §5. Each tag's `label` is what evidence.com sees. |
| `primary_officer` | `Case.primary_investigator_id` + resolved display name + badge | Already populated post-F19. |
| `report.filename` | `Report` PDF export filename | We generate this. |
| `report.title` | `Report.title` | Verbatim. |
| `report.signed_at` | `Report.signature.signed_at` | F19. |
| `report.signer` | `Report.signature.user_id` + `display_name` + `badge_number` | F19. |
| `report.ai_programs` | `Report.ai_programs_used[]` | §13663(a)(1). |
| `report.disclosure_text` | hard-coded statutory string | Already verbatim on every PDF page. Carried in the export payload for redundancy. |
| `report.content_sha256` | `Report.signature.content_sha256` | Tamper-evidence on the destination side. |
| `report.first_ai_draft_text` | `Report.first_ai_draft_text_snapshot` | §13663(b) lives on the destination too. |
| `attachments[].sha256` | `Document.sha256` / `Report` chain.pdf hash | Per-file integrity. |
| `attachments[].original_filename` | `Document.original_filename` | Verbatim. |
| `attachments[].mime_type` | `Document.mime_type` | Verbatim. |
| `attachments[].external_id` | `Document.external_id` (new) | Stable dedupe key. |
| `chain_of_custody.export_url` | chain.pdf endpoint | Already generated per signed report. |
| `evidence_com_asset_id` | `Report.evidence_com_asset_id` (new, populated on first successful push) | Empty until integration ships. Reserved field. |

### 13.2 Schema additions to ship in this batch

These additions are **cheap now, expensive later** — adding them after a year of real cases means a backfill migration. Cost-of-delay justifies the work now.

**`Case`:**
- `date_of_incident: DateField()` — optional; UI prompt at case creation.
- `external_id: StringField(unique_with="tenant_id")` — set on create to `{agency_ori}:{case_number}`. Index on it.
- `agency_ori_snapshot: StringField()` — captured from env at creation; never re-read after.
- `last_activity_at: DateTimeField()` — denormalized; touched on doc/media register, message send, report sign/export.

**`Report`:**
- `external_id: StringField(unique_with="tenant_id")` — set on create to `{case.external_id}:report:{seq}`.
- `evidence_com_asset_id: StringField(default="")` — reserved field; integration populates later.
- `evidence_com_pushed_at: DateTimeField()` — same.

**`Document` and `MediaInput`:**
- `external_id: StringField(unique_with="tenant_id")` — set on create to `{case.external_id}:doc:{id}` or `:media:{id}`.

**Not added now (intentionally):**
- `Tag` and `TagAssignment` — Phase B. The data plan accommodates them by reserving the `tags` field-name in payload composition; the schema lands when the UI lands.
- `Person` / `PersonMention` — Phase C.
- evidence.com category mapping table — lives in the future provider, not in the data model. The mapping is a deployment configuration concern.

### 13.3 Naming conventions to lock now

These hurt to change later because they appear on signed PDFs, audit events, and (eventually) outbound JSON to evidence.com.

| Concept | Canonical name on the wire | Notes |
|---|---|---|
| The agency's federal identifier | `agency_ori` | Always lowercase snake_case. Not "ORI", not "agencyOri". |
| The agency's display name | `agency_name` | Matches `COLDCASE_AGENCY_NAME` env. |
| Stable per-artifact id | `external_id` | Not `evidence_id`, not `cad_id` — generic enough to survive future destination systems too. |
| The statute citation | `§13663(...)` | Always with the section symbol, always parens for sub-divisions. Already enforced in PDF + 403 bodies. |
| First AI draft snapshot | `first_ai_draft_text_snapshot` | Already canonical in `Report`. Don't shorten. |
| Officer signature attestation timestamp | `signed_at` | Singular noun + `_at` suffix matches every other timestamp field. |

### 13.4 What this buys

When evidence.com integration ships, the implementation is approximately:

```python
def publish(report: Report) -> str:
    payload = build_payload(report)        # already-present fields, no joins to fix
    asset_id = evidence_com_client.post(payload, files=[...])
    report.evidence_com_asset_id = asset_id
    report.evidence_com_pushed_at = datetime.utcnow()
    report.save()
    case_audit.log_user_event(user, event_type=EVIDENCE_COM_PUBLISHED, ...)
    return asset_id
```

No data backfill. No schema migration on a live agency database. No "we'll have to bump every artifact" awkwardness.

---

## 12. Where to look next, after sign-off

If we go forward with Phase A, the first PR to write is the **tabbed case workspace shell** in `src/features/cases/pages/CaseDetailPage.tsx`. That single change is the foundation everything else hangs off — once tabs exist, the rest of Phase A is moving existing components into them and adding the hero band. The Report workspace promotion (drawer → route) is the second PR. Dashboard is third.

Backend changes for Phase A fit in one PR: `?mine` filter, last-activity derived field, and surfacing the preflight result in the admin panel.

I'll wait for your direction on:
- Which phase to start (default: Phase A as proposed),
- Whether the IA proposal matches what you'd show the detective sponsor,
- Any of the 5 open design questions in §11.
