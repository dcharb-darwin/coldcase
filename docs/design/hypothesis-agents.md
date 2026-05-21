# Multi-agent hypothesis workflow — design doc

**Status:** Draft for review, 2026-05-20.
**Supersedes:** the single-agent flow shipped in PRD v0.10.0.
**Replaces (will replace):** the "Generator-only" suggest endpoint shipped in `2a8cc6d` once this design lands.

---

## Why this exists

The hypothesis pipeline shipped in v0.10.0 is **one LLM call followed by another LLM call**, both with the same incentive: "find evidence that fits." That's the sycophancy trap — the AI agrees with the detective's framing because the prompt asked it to extract hypotheses, then agrees with itself when asked to check evidence. The detective gets a confidence boost, not a stress test.

Real investigative thinking depends on **friction**. A cold-case veteran disagrees with the detective; defense counsel hammers the weakest link; the case file itself sometimes contradicts the working theory. A useful AI assistant has to simulate that pressure or it's worse than nothing — it manufactures false confidence the detective then signs their name to.

This doc lays out a small multi-agent design where agents have **structurally different inputs and incentives**, so disagreement comes from the system shape, not from prompt-engineering tricks.

---

## Agent roster

Five agents could exist. Three earn their keep.

### Kept

#### 1. `generator` — brain-dump → hypotheses *(existing, mild revision)*

- **Input:** detective brain dump + case docs
- **Output:** 3–6 falsifiable hypotheses with title, body, rationale
- **Incentive:** structure unstructured speech; preserve detective's voice
- **Failure mode:** parrots the detective without questioning
- **Mitigation in revised prompt:** "include at least one hypothesis the detective did not raise but the documents suggest" — forces de-anchoring from the brain dump

#### 2. `de_novo_generator` — case docs alone → hypotheses *(new)*

- **Input:** case docs ONLY, no brain dump
- **Output:** 3–6 hypotheses framed as **questions the documents raise but no one has answered**
- **Incentive:** fresh-eyes perspective — what would an investigator see if they hadn't already formed a theory?
- **When the detective uses it:** stuck, suspicious of their own framing, onboarding to a case they didn't open
- **Why it's distinct from `generator`:** different INPUT (no brain dump). Single-agent flow couldn't tell these apart; multi-agent makes the difference explicit and chip-labels it on the artifact (`origin = ai_de_novo`)

#### 3. `red_team` — challenge one specific hypothesis *(new — the key fix)*

- **Input:** ONE target hypothesis + case docs + other hypotheses on the case (cross-talk)
- **Output:**
  - **Counter-evidence** — passages in the docs that contradict the hypothesis
  - **Alternative explanations** — other hypotheses that fit the *same* evidence equally well
  - **Bias flags** — named cognitive biases this hypothesis reflects (closed vocab, see below)
  - **Logical gaps** — what the hypothesis assumes but does not establish
- **Incentive:** ATTACK. The system prompt is explicit: "your job is to disprove this. If you cannot find anything, return an empty array; do not invent."
- **Failure mode:** invents strawmen contradictions to look productive
- **Mitigation:** counter-evidence requires `source_doc_id` and `excerpt` that we validate against real documents at parse time (same guard as `suggest_inferred_mentions`)

### Rejected (intentionally)

#### `prosecutor` / `defense` framing — *redundant with red_team*

Tempting because lawyers are recognizable framing. But "defense" IS red-team, and "prosecutor" is what the original generator already does. Adding the costume would dilute the red-team prompt and double the LLM cost for no new signal.

#### `pattern_matcher` against historical cold cases — *handled elsewhere*

We already have tag-Jaccard similar-cases on the Brief tab. A separate agent matching free-text patterns would be impressive in a demo and useless in practice — the agency doesn't have a curated pattern library, and shipping one would require labeling thousands of historical cases.

#### `synthesizer` / `arbitrator` — *defeats the purpose*

A tempting agent that reads generator output + red-team output and "renders a balanced view." Skip. The detective should see the disagreement raw. Smoothing it over reintroduces sycophancy through the back door — now with extra latency.

#### `steel_manner` — *wrong direction*

Strengthens hypotheses by stating their strongest form. Useful for academic debate, harmful here — the detective doesn't need their working theory polished, they need it stress-tested.

---

## Hypothesis origin — first-class metadata

Every `Hypothesis` carries an `origin` enum that determines its chip in the UI and lets later compliance review trace lineage:

| Value | Meaning | UI chip |
|---|---|---|
| `human_typed` | Detective wrote it directly into the editor, no AI involved | 👤 Human |
| `ai_from_braindump` | Generator produced it from a detective brain dump | 🤖 AI · brain dump |
| `ai_de_novo` | De-novo generator produced it from case docs alone | 🤖 AI · de-novo |
| `ai_alternative` | Red-team proposed it as an alternative to another hypothesis | 🤖 AI · alternative → [parent] |

The `ai_alternative` row carries `parent_hypothesis_id`. A hypothesis can have many children (red-teaming the same parent multiple times produces multiple alternative branches); a child has exactly one parent.

This is more than UI sugar — it tells the city attorney **which AI agent surfaced an artifact** during a PRA response or trial discovery. Anti-sycophancy is partly a UX problem and partly an audit problem.

---

## Bias-flag vocabulary

Closed vocabulary so the LLM cannot invent new biases. Each flag is a chip with a tooltip explaining the bias in one sentence.

| Slug | Label | Tooltip |
|---|---|---|
| `confirmation_bias` | Confirmation bias | Evidence selected to support the conclusion rather than test it |
| `anchoring` | Anchoring | Conclusion anchored on the first witness statement or first hypothesis raised |
| `narrative_fallacy` | Narrative fallacy | Story is coherent but doesn't fit all the evidence |
| `availability_bias` | Availability bias | Weights vivid or recent evidence more than reliable evidence |
| `groupthink` | Groupthink | Agrees with prior investigators' framing without an independent check |
| `motivated_reasoning` | Motivated reasoning | Conclusions appear shaped by a desired outcome |
| `survivorship_bias` | Survivorship bias | Ignores evidence that wasn't preserved or didn't make it into the file |
| `recency_bias` | Recency bias | Weights newer evidence more than reliable older evidence |
| `attribution_error` | Attribution error | Infers motive or character from situation alone |

Closed vocab is the same pattern as `Tag.slug` — the LLM can return only these strings; anything else is dropped at parse time. The vocabulary lives in `services/bias_vocab.py` so it's editable by an attorney without touching code.

---

## Endpoints

```
POST /cases/{id}/brain-dumps/{id}/suggest-hypotheses
  -> generator  (existing — mild prompt revision)

POST /cases/{id}/hypotheses/generate
  -> de_novo_generator  (new)
  Returns same shape as suggest-hypotheses; detective accepts each into
  a Hypothesis with origin=ai_de_novo. No brain dump required.

POST /cases/{id}/hypotheses/{id}/red-team
  -> red_team  (new)
  Returns:
    {
      counter_evidence: [{kind: contradicting, excerpt, rationale,
                          source_doc_id, source_doc_filename}],
      alternatives:     [{title, body, rationale}],
      bias_flags:       ["confirmation_bias", ...],   // closed vocab
      logical_gaps:     ["string"],
      model:            "gpt-4o-mini-…"
    }
  Audited as HYPOTHESIS_RED_TEAMED.
  Detective then:
    - Accepts a counter_evidence entry into hypothesis.findings via the
      existing /findings endpoint (kind=contradicting auto-set).
    - Accepts an alternative via POST /cases/{id}/hypotheses with
      origin=ai_alternative + parent_hypothesis_id=this_id.
    - bias_flags and logical_gaps persist on the parent hypothesis
      itself (new fields) so subsequent reviewers see them at-a-glance.
```

Audit events added:

- `HYPOTHESIS_GENERATED_DE_NOVO`
- `HYPOTHESIS_RED_TEAMED`

(`HYPOTHESIS_CREATED`, `HYPOTHESIS_ACCEPTED_FROM_AI`, `HYPOTHESIS_FINDING_ACCEPTED`, `HYPOTHESIS_STATUS_CHANGED` already exist from v0.10.0.)

---

## Model changes

```python
class HypothesisOrigin(str, Enum):
    HUMAN_TYPED        = "human_typed"
    AI_FROM_BRAINDUMP  = "ai_from_braindump"
    AI_DE_NOVO         = "ai_de_novo"
    AI_ALTERNATIVE     = "ai_alternative"


class Hypothesis(MEDocument):
    # ...existing fields
    origin = StringField(
        required=True, default=HypothesisOrigin.HUMAN_TYPED.value,
        choices=[o.value for o in HypothesisOrigin],
    )
    parent_hypothesis_id = StringField(default="")   # for AI_ALTERNATIVE
    bias_flags = ListField(StringField(), default=list)  # closed vocab, accrues across red-team runs
    logical_gaps = ListField(StringField(), default=list)
    red_team_count = IntField(default=0)             # how many times challenged
```

Existing rows: backfill `origin` based on `proposed_by_model` field — populated string ⇒ `ai_from_braindump`, empty ⇒ `human_typed`. One-time script in `services/seed_defaults.py` lifespan.

---

## UI

Two surfaces change on the Hypothesis tab:

### Composer area gets a new sibling button

```
┌─ Brain dump → hypotheses ────────────────────────────┐
│  [Type | Record | Upload]                            │
│  textarea / recorder / dropzone                      │
│  [Capture + suggest hypotheses]                      │
├─ OR ─────────────────────────────────────────────────┤
│  No brain dump yet?                                  │
│  [Generate hypotheses from case documents]           │
│  Fresh-eyes perspective — what would a new           │
│  investigator notice? AI reads the docs without      │
│  your framing.                                       │
└──────────────────────────────────────────────────────┘
```

### Hypothesis card gets origin chip + Challenge button

```
┌─ [Investigating] 👤 Human ──────────── [status ▼]──┐
│ Brenda Aragón's timeline doesn't match patrol log  │
│ Aragón says 11pm; patrol log puts the car at the   │
│ riverfront at 10:40 — 20-minute gap unexplained.   │
│ Rationale: detective's brain dump, 2026-05-20      │
│                                                    │
│ ⚠ Bias flags: anchoring · narrative_fallacy        │
│ ▸ Logical gaps: assumes Aragón's clock was        │
│   accurate (no independent timestamp)             │
│                                                    │
│ Findings on file (2):                              │
│   contradicting "patrol log entry 22:40..."        │
│   gap "no independent timestamp..."                │
│                                                    │
│ [Check evidence]  [Challenge this]  [Delete]       │
└────────────────────────────────────────────────────┘
```

### Challenge results render in three columns

```
┌─ Red-team — model: gpt-4o-mini ────────────────────┐
│                                                    │
│  Counter-evidence  │ Alternatives    │ Bias flags  │
│  (3)               │ (2)             │ + gaps      │
│  ─────────────────│────────────────│──────────── │
│  "patrol log…"    │ Aragón clock    │ anchoring   │
│  [Add to record]  │  was off        │             │
│                   │ [Investigate]   │ narrative   │
│  "interview…"     │                 │ fallacy     │
│  [Add to record]  │ Different car   │             │
│                   │  at 10:40       │ gap: ...    │
│  "log shows…"     │ [Investigate]   │             │
│  [Add to record]  │                 │             │
│                                                    │
└────────────────────────────────────────────────────┘
```

Buttons:
- **Add to record** — appends a contradicting `HypothesisFinding` to the parent
- **Investigate** — creates a new Hypothesis with `origin=ai_alternative`, `parent_hypothesis_id=parent.id`, status=investigating
- Bias flags + gaps are display-only here; they're already persisted on the parent on first run

The card shows the parent ↔ children relationship via a small "↗ alternative to: …" link on each child, and a "+N alternatives" count on each parent.

---

## Anti-sycophancy design choices, listed plainly

| Choice | Reason |
|---|---|
| Separate `red_team` agent with attack-only prompt | Distinct incentive at the system-prompt level, not a hint inside one mega-prompt |
| Closed bias-flag vocabulary | LLM can't invent flags that flatter the detective ("hypothesis is rigorous") |
| No `synthesizer` agent | The detective sees raw disagreement, not a smoothed-over verdict |
| Counter-evidence requires real `source_doc_id` | Prevents fabricated contradictions |
| Generator prompt revised: "include at least one hypothesis the detective did not raise" | Forces the generator off the brain dump's anchor |
| Origin chip on every hypothesis | Detective can tell at a glance whose framing they're looking at |
| AI-alternative hypotheses keep a `parent_hypothesis_id` link | Lineage is preserved for review; nothing is "just AI's idea" without provenance |
| All red-team outputs are LLM suggestions — none auto-persist | Detective decides what's worth keeping; agent never writes for them |

---

## Cost + latency

| Call | Cost (gpt-4o-mini) | Latency |
|---|---|---|
| `generator` | ~$0.002 | 4–8s |
| `de_novo_generator` | ~$0.002 | 5–10s |
| `red_team` (per hypothesis) | ~$0.003 | 6–12s |
| `check_hypothesis` (existing) | ~$0.003 | 6–10s |

Typical case: brain-dump → generate (1) → accept 3 hypotheses → red-team each (3) → check each (3) → ~10 LLM calls per case ≈ $0.03. Trivially small.

Latency matters more than cost — every call is on the UX critical path. The "Reading docs…" placeholder pattern shipped for inferred-mentions (clear cached list, italic message during fetch) applies here verbatim.

---

## Open questions for review

1. **Should bias-flag vocabulary be editable per-tenant?** Default: shipped vocab, hard-coded. Per-tenant override only when an agency lawyer asks. Vote: ship hard-coded; revisit when a tenant actually requests.

2. **Should red-team run automatically when a hypothesis is created from AI?** Argument for: catches sycophancy immediately. Argument against: doubles LLM cost on every accept, and the detective may want to think before being challenged. Vote: manual button (matches accept-each-individually pattern).

3. **Should the de-novo generator run automatically on case open?** Argument for: gives an instant fresh-eyes view. Argument against: cost on every open + confuses detective with hypotheses they didn't ask for. Vote: manual.

4. **How long should bias flags persist?** Forever on the hypothesis (so reviewers years later see what the AI flagged). Optional "dismiss this bias flag" by the detective with a one-line justification, audited. Vote: persist forever, no dismissal mechanism — bias flags belong in the record.

5. **Should accepted alternatives inherit the parent's status?** No. Status=investigating fresh — the detective is choosing to pursue the alternative, which is a fresh investigation, not a parallel one.

6. **Should hypothesis lifecycle events (status changes, red-team runs) appear on the case Timeline tab?** Yes — they're case-affecting actions. Add `hypothesis.*` to the timeline color map. Out of scope for the initial multi-agent PR; track for a follow-up.

---

## What ships in PR

One PR labeled `feat: multi-agent hypothesis (red-team + de-novo)`:

- Model: `Hypothesis.origin` + `parent_hypothesis_id` + `bias_flags` + `logical_gaps` + `red_team_count`
- Backfill: lifespan migration setting `origin` on existing rows
- Endpoints: `/hypotheses/generate`, `/hypotheses/{id}/red-team`
- Audit event types: `HYPOTHESIS_GENERATED_DE_NOVO`, `HYPOTHESIS_RED_TEAMED`
- Service: `services/bias_vocab.py` holds the closed list + tooltips
- Generator prompt revision (add the "include one the detective didn't raise" clause)
- UI: origin chip, de-novo button, Challenge button + three-column results panel, bias-flag chips on parent card

What's **out** of this PR:
- Timeline integration of hypothesis events
- Per-tenant bias vocab override
- "Auto red-team on accept" toggle
