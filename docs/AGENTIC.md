# Agentic Behavior

Patterns for AI assistants that live **inside** a Launchpad app (e.g., the admin permission assistant, an SOP finder, a scheduler recommender). Developer-time agent rules are in `CONVENTIONS.md`; UX rules for agent surfaces are in `PRINCIPLES.md` part 2.

## 1. The Proposer → Reviewer pattern

High-stakes AI actions — permission changes, bulk operations, terminal state transitions — run through two model calls before anything reaches the user.

```
 ┌──────────┐     ┌──────────┐     ┌──────┐
 │ Proposer │ ──► │ Reviewer │ ──► │  UI  │ ──► user clicks Apply per action
 └──────────┘     └──────────┘     └──────┘
```

**Proposer**: receives user prompt + app manifest (permissions, roles, scope types). Output is a structured JSON array of proposed actions, each with an `action` (e.g. `create_role`, `assign_role`, `create_mapping`), validated against the manifest.

**Reviewer**: receives the proposer's output + the full context the proposer saw + the manifest. Output is the same shape but with `review_verdict` (`approved` / `modified` / `rejected` / `added`) per action, plus `review_reason`.

**UI**: renders both verdicts. User sees what the proposer drafted, what the reviewer changed, and applies per-action. No auto-apply.

Reference implementation: `server-py/services/admin_assistant.py`.

**This pattern is how you discover roles.** See [`ROLES.md`](ROLES.md) Stage 2 — the assistant translates "give HR read-only access to Operations" into validated `create_role` + `assign_role` proposals. That's the intended workflow for evolving a manifest, not an afterthought.

**Config:**
- `ADMIN_ASSISTANT_MODEL` — proposer. Default `qwen3.6:35b-a3b-nvfp4`.
- `ADMIN_REVIEWER_MODEL` — reviewer. Defaults to the proposer; override for stricter review (e.g. `qwen3.5:27b`).
- `ADMIN_REVIEWER_ENABLED=0` disables the reviewer pass (not recommended outside local experimentation).

## 2. The LLM is a translator, not an authorizer

Every action an LLM proposes is **validated against app constraints before it reaches the DB**. If a model hallucinates a permission name (`"sop.delete_everything"`), validation rejects it. If a model proposes an action that would escalate the caller's own privileges, the admin router's server-side permission check rejects it.

Validation layers:
1. JSON schema on the LLM response (malformed → skip).
2. Manifest validation per action (unknown permission / role / scope type → action marked invalid, not applied).
3. Server-side permission re-check in the admin router (same check a direct API call would hit).

There is no code path where an LLM hallucination reaches the DB. Write code so that remains true.

## 3. Structured output, not free-form chat

AI assistants that influence app state return structured JSON validated by `pydantic` on the backend and typed in TypeScript on the frontend. Free-form chat is fine for user dialogue; it's not fine as a state-mutation channel.

```python
@dataclass
class ProposedAction:
    action: Literal["create_role", "assign_role", "create_mapping", "clarification"]
    summary: str
    valid: bool
    params: dict
    review_verdict: Literal["approved", "modified", "rejected", "added"] = "approved"
    review_reason: str = ""
    original_summary: str = ""
    original_params: dict = field(default_factory=dict)
```

## 4. Clarifying questions

If the proposer can't decide between two reasonable readings of a prompt, it emits an action of type `clarification` instead of guessing. The UI renders it differently (a question, not a proposal), and the user answers in the next turn.

This keeps the loop tight: the user sees "I understood X or Y — which?" rather than "I applied X" and having to undo.

## 5. Permission surface for assistants

Every AI assistant is gated by a permission in the app manifest. The admin assistant lives behind `admin.view`. SOP find-by-task lives behind `sop.find_by_task`. The frontend renders the assistant only when `usePermission("...")` returns true.

Assistants never bypass app permissions — they operate with the calling user's permission context, not a service account.

## 6. Impersonation

Super-admins can impersonate other users for support purposes. When impersonating:
- Every request carries `X-Impersonate-User-Id: <user-id>` (axios request interceptor).
- The backend middleware resolves the impersonated user's context, not the SA's.
- An impersonation banner renders above the app shell showing who the SA is acting as.
- Audit entries include both `actor_id` (the SA) and the impersonated user id in metadata.

Impersonation is logged as `impersonate_start` / `impersonate_end` in the audit trail.

## 7. Temperature

`temperature=0.1` is the default for all JSON-mode calls. Higher temperatures produce parse failures and creative hallucinations.

If an assistant needs creativity (e.g., drafting human-readable reasons), split the call: structured action at 0.1, free-form reason text at a higher temp with the actions as input context.

## 8. Timeouts

`ADMIN_ASSISTANT_TIMEOUT_S=180` default. Two-agent chains on Apple Silicon can run 30–90s; reviewer adds up to another 60s. Generous by default; set lower in env for fast-fail behavior with smaller models.

## 9. Observability

Every assistant call is logged at INFO with: model, endpoint, input token count estimate, latency, output size, action count. No user-supplied prompt text in logs (PII).

Failures log at WARN (transport) / ERROR (unexpected response shape).

## 10. Not goals

- **Chat history persistence.** Assistants are single-turn by default. Multi-turn is a discrete feature with its own PRD, not a default.
- **Streaming output.** JSON-mode responses are returned whole. Streaming arrives with the first feature that needs it.
- **Model auto-selection.** Every assistant has a fixed env-driven model. The user picks the model by editing `.env`, not at runtime.
- **RAG across arbitrary documents.** Assistants operate on structured app state (manifests, routes, data), not free-form corpora. RAG is out of scope until an app explicitly needs it.
