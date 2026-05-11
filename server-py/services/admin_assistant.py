"""
AI assistant for permission management.

Natural-language admin prompts ("give HR access to update only HR SOPs")
→ validated structured proposals (create_role, assign_role, create_mapping).

Design notes:
- LLM is used for *translation*, not authorization. Every proposed action is
  validated against the AppManifest before it's returned to the UI, and each
  action is applied via the normal POST /admin/* endpoint (which re-enforces
  the same rules). There's no code path where a hallucinated permission
  string or a privilege-escalating action reaches the DB.
- No auto-apply: the UI requires an explicit click per action.
- Model is configurable via env (`ADMIN_ASSISTANT_MODEL`, default
  qwen3.6:35b-a3b-nvfp4 — see knowledge/launchpad/ollama-models.md).
- Ollama's JSON mode (`format: "json"`) is used to keep output parseable.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from .ollama_client import OllamaError, call_ollama_json

logger = logging.getLogger(__name__)


# ── Config ──────────────────────────────────────────────────────────────────

ADMIN_ASSISTANT_MODEL = os.environ.get("ADMIN_ASSISTANT_MODEL", "qwen3.6:35b-a3b-nvfp4")
# ^ proposer default. qwen3.6:35b-a3b-nvfp4 is the current Launchpad standard
# (see knowledge/launchpad/ollama-models.md) — fast MoE (active-3B) with strong
# JSON compliance. Fall back to qwen3:14b if the 35b-a3b isn't pulled yet.
# Override to qwen3.5:27b for higher-quality (slower) reviewer-tier calls.

# The reviewer sees the proposer's output + full app context and critiques it
# before the admin sees anything. Should usually be at least as capable as
# the proposer. Same name = one-model-deployed convenience; bigger = more
# skeptical and better at spotting subtle mistakes.
ADMIN_REVIEWER_MODEL = os.environ.get("ADMIN_REVIEWER_MODEL", ADMIN_ASSISTANT_MODEL)
ADMIN_REVIEWER_ENABLED = os.environ.get("ADMIN_REVIEWER_ENABLED", "1") != "0"

ADMIN_ASSISTANT_TIMEOUT_S = float(os.environ.get("ADMIN_ASSISTANT_TIMEOUT_S", "180"))
# ^ generous default: 14B+ models with long system prompts + two-agent chain
# (proposer + reviewer) can take 30–90s on Apple Silicon. Set 60 via env for
# smaller models if you want faster-fail.


# ── Output schema ───────────────────────────────────────────────────────────


@dataclass
class ProposedAction:
    """One action the assistant wants to take. Rendered as a card in the UI.

    `review_*` and `original_*` fields are populated by the reviewer agent
    after it critiques the proposer's draft. They're empty / defaults when
    the reviewer is disabled (`ADMIN_REVIEWER_ENABLED=0`).
    """

    kind: str                          # "create_role" | "assign_role" | "create_mapping"
    body: dict                         # payload that POSTs to /admin/{endpoint}
    summary: str                       # human sentence for the UI card
    warnings: list[str]                # validator notes (e.g. "role doesn't exist yet")
    valid: bool                        # False → card shows no Apply button

    # Reviewer annotations (populated by the second-stage agent):
    review_verdict: str = "approved"   # approved | modified | rejected | added
    review_notes: str = ""             # why the reviewer reached this verdict
    original_body: dict | None = None  # proposer's body if reviewer modified/rejected
    original_summary: str = ""         # proposer's summary if reviewer modified/rejected

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "body": self.body,
            "summary": self.summary,
            "warnings": self.warnings,
            "valid": self.valid,
            "review_verdict": self.review_verdict,
            "review_notes": self.review_notes,
            "original_body": self.original_body,
            "original_summary": self.original_summary,
        }


# ── Prompt builder ──────────────────────────────────────────────────────────


def _build_context_block(
    manifest_dict: dict,
    roles: list[dict],
    scope_options: dict[str, list[dict]],
    app_identity: str = "",
    current_mappings: list[dict] | None = None,
    current_assignment_count: int = 0,
) -> str:
    """Render the live app state the LLM reasons over. Terse on purpose so
    7B/8B local models don't lose the plot in long contexts."""

    identity = app_identity.strip()
    identity_block = f"## About this app\n{identity}\n" if identity else ""

    # Permissions — include description so the LLM knows what each one *does*.
    perm_lines = []
    for pid, meta in manifest_dict.get("permissions", {}).items():
        label = meta.get("label", pid)
        desc = meta.get("description", "")
        line = f'- "{pid}": {label}'
        if desc and desc != label:
            line += f" — {desc}"
        perm_lines.append(line)
    perms_block = "\n".join(perm_lines)

    role_lines = []
    for r in roles:
        desc = (r.get("description") or "").strip()
        perms = ", ".join(r.get("permissions", []) or [])
        line = f'- "{r["name"]}"'
        if desc:
            line += f": {desc}"
        line += f"\n  permissions: [{perms}]"
        role_lines.append(line)
    roles_block = "\n".join(role_lines) if roles else "(none)"

    scope_types_block_lines = []
    for st in manifest_dict.get("scope_types", []):
        st_desc = (st.get("description") or "").strip()
        line = f'- "{st["id"]}" ({st.get("label", st["id"])})'
        if st_desc:
            line += f" — {st_desc}"
        scope_types_block_lines.append(line)
    scope_types_block = "\n".join(scope_types_block_lines) if scope_types_block_lines else "(none — tenant-wide only)"

    scopes_block_parts = []
    for stype, items in scope_options.items():
        if not items:
            continue
        scopes_block_parts.append(f"Available {stype}s (use `scope_id` when scoping to one):")
        for it in items[:50]:
            name = it.get("name") or it.get("title") or "(unnamed)"
            scopes_block_parts.append(f'  - id="{it["id"]}" name="{name}"')
    scopes_block = "\n".join(scopes_block_parts) if scopes_block_parts else "(no scoped resources known yet)"

    mappings_lines = []
    for m in (current_mappings or []):
        mappings_lines.append(
            f'- {m["match_type"]}="{m["match_value"]}" → role "{m.get("role_name")}"'
            f' scope={m.get("scope_type") or "tenant-wide"}:{m.get("scope_id") or "-"}'
        )
    mappings_block = "\n".join(mappings_lines) if mappings_lines else "(none yet)"

    return f"""{identity_block}
## Available permissions (use these exact id strings; never invent)
{perms_block}

## Existing roles (prefer reusing these over creating new ones)
{roles_block}

## Scope types
{scope_types_block}

## Scope resources
{scopes_block}

## Mappings already in place (don't create duplicates)
{mappings_block}

## State
Direct role assignments active in this tenant: {current_assignment_count}
"""


SYSTEM_PROMPT = """You are a permissions assistant for a line-of-business app.
Translate an administrator's plain-English request into a concrete set of
actions they can apply with one click — or, when the request is ambiguous,
ask clarifying questions instead of guessing.

You can propose three kinds of actions:

1. **create_role** — define a new custom role with a permission set.
   Use only when existing roles don't already match what the admin wants.
   Fields: { "name", "description", "permissions": [permission_id, ...] }

2. **assign_role** — grant a specific named user a role, optionally scoped
   to one resource.
   Fields: { "user_id", "role_name", "scope_type", "scope_id" }

3. **create_mapping** — auto-assign a role to everyone matching an identity
   claim. This is the CORRECT choice for group-wide or department-wide
   requests ("give HR", "anyone in IT", "people in the Compliance AD group").
   Fields: { "match_type": "ad_group" | "department",
             "match_value": <the group or department name>,
             "role_name", "scope_type", "scope_id" }

Field discipline (common source of errors):
  - match_type: ONLY "ad_group" or "department". Never "owner_group" or any
    scope type. Scope types go in scope_type.
  - match_value: the AD group name or department name (a string like
    "HR-Managers", "IT", "Compliance-Reviewers"), not a role name.
  - scope_type: one of the ids from the Scope types list (e.g.
    "owner_group", "sop").
  - scope_id: an id from the matching Scope resources list.

Core rules:
- Only use permission ids from the catalog. Never invent permissions.
- Prefer reusing existing roles. Only create a new role when none match.
- Group-wide / department-wide → create_mapping, NOT assign_role per user.
- Resolve human names to ids using the Scope resources list. "HR library"
  → find an owner_group named "HR" or similar and use its id.
- Multi-action patterns are fine: "read all + edit only HR" = two actions
  (e.g., cross_library_reader tenant-wide + library_editor scoped to HR).

## When to ask questions instead of proposing

If the request is genuinely ambiguous — a critical piece is missing and
guessing would risk over- or under-granting access — emit `questions`
rather than (or in addition to) actions. Examples of things to ask about:
- The admin said "give the operations team access" but no owner_group
  named "Operations" exists, and there are multiple candidate groups.
- Unclear whether scoping is needed ("give Jane edit access" — to what?).
- A non-trivial new role is implied but no name/description is specified.

Don't ask about trivia. If context makes the answer obvious, just act.

## Few-shot examples

EXAMPLE 1 — group-wide read:
  Admin: "Everyone in the HR-Managers AD group should be able to read all SOPs"
  Output:
    { "understanding": "Auto-assign tenant-wide read to the HR-Managers AD group",
      "actions": [
        { "kind": "create_mapping",
          "match_type": "ad_group", "match_value": "HR-Managers",
          "role_name": "reader",
          "scope_type": null, "scope_id": null }
      ],
      "questions": [], "notes": "" }

EXAMPLE 2 — the HR/IT tiered pattern:
  Admin: "Give the HR department read access to every SOP but edit access
          only within the HR library"
  Output:
    { "understanding": "Tiered access for HR department: read everywhere,
                         edit only in the HR library",
      "actions": [
        { "kind": "create_mapping",
          "match_type": "department", "match_value": "HR",
          "role_name": "cross_library_reader",
          "scope_type": null, "scope_id": null },
        { "kind": "create_mapping",
          "match_type": "department", "match_value": "HR",
          "role_name": "library_editor",
          "scope_type": "owner_group", "scope_id": "<id of HR library>" }
      ],
      "questions": [], "notes": "" }

EXAMPLE 3 — ambiguous, ask a question:
  Admin: "Let the ops team manage stuff"
  Output:
    { "understanding": "Grant some kind of access to an 'ops' group — scope
                         and level unclear",
      "actions": [],
      "questions": [
        "Which owner_group is 'ops' — Operations? There's no exact match.",
        "What should 'manage' mean — full edit, or also include accept/delete?",
        "Is this for the whole Operations AD group, or specific users?"
      ],
      "notes": "" }

## Output format

ONE JSON object exactly:
{
  "understanding": "brief restatement of what the admin asked for",
  "actions": [ { "kind": "...", ... action fields ... }, ... ],
  "questions": [ "clarifying question 1", "clarifying question 2" ],
  "notes": "optional — caveats"
}

No prose outside the JSON. No code fences. JSON only."""


def build_user_prompt(context_block: str, admin_request: str) -> str:
    return f"""{context_block}

Admin request:
{admin_request}

Respond with JSON only."""


# ── Ollama call ─────────────────────────────────────────────────────────────


# Kept as an alias so existing `except AssistantError` callers still work;
# all new code should catch OllamaError directly.
AssistantError = OllamaError


# ── Validation ──────────────────────────────────────────────────────────────


def _resolve_role_id(role_name: str, roles: list[dict]) -> str | None:
    for r in roles:
        if r["name"] == role_name:
            return r["id"]
    return None


def validate_action(action: dict, manifest_dict: dict, roles: list[dict]) -> ProposedAction:
    """Turn a raw LLM action into a validated ProposedAction.
    The UI still shows invalid actions (with warnings + no Apply button) so the
    admin can see what the LLM misunderstood."""
    kind = action.get("kind", "")
    warnings: list[str] = []
    valid = True

    if kind == "create_role":
        name = (action.get("name") or "").strip()
        description = (action.get("description") or "").strip()
        perms = list(action.get("permissions") or [])
        catalog = set(manifest_dict.get("permissions", {}).keys())
        unknown = [p for p in perms if p not in catalog]
        if unknown:
            warnings.append(f"Unknown permissions (dropped): {unknown}")
            perms = [p for p in perms if p in catalog]
        if not name:
            warnings.append("Missing role name")
            valid = False
        if any(r["name"] == name for r in roles):
            warnings.append(f"Role '{name}' already exists — apply will fail")
            valid = False
        summary = f"Create role {name!r} with {len(perms)} capabilities"
        return ProposedAction(
            kind="create_role",
            body={"name": name, "description": description, "permissions": perms},
            summary=summary,
            warnings=warnings,
            valid=valid,
        )

    if kind == "assign_role":
        user_id = (action.get("user_id") or "").strip()
        role_name = (action.get("role_name") or "").strip()
        scope_type = (action.get("scope_type") or "").strip() or None
        scope_id = (action.get("scope_id") or "").strip() or None
        role_id = _resolve_role_id(role_name, roles)
        if not user_id:
            warnings.append("No user specified — apply will need one filled in")
            valid = False
        if not role_id:
            warnings.append(f"Role '{role_name}' not found — will fail on apply")
            valid = False
        if scope_type and scope_type not in {s["id"] for s in manifest_dict.get("scope_types", [])}:
            warnings.append(f"Unknown scope_type '{scope_type}'")
            valid = False
        if scope_type and not scope_id:
            warnings.append(f"scope_type '{scope_type}' set but no scope_id")
            valid = False
        where = f" scoped to {scope_type}={scope_id}" if scope_id else " tenant-wide"
        summary = f"Assign {role_name!r} to {user_id or '<user?>'}{where}"
        return ProposedAction(
            kind="assign_role",
            body={"user_id": user_id, "role_id": role_id, "scope_type": scope_type, "scope_id": scope_id},
            summary=summary,
            warnings=warnings,
            valid=valid,
        )

    if kind == "create_mapping":
        match_type = (action.get("match_type") or "").strip()
        match_value = (action.get("match_value") or "").strip()
        role_name = (action.get("role_name") or "").strip()
        scope_type = (action.get("scope_type") or "").strip() or None
        scope_id = (action.get("scope_id") or "").strip() or None
        role_id = _resolve_role_id(role_name, roles)
        if match_type not in ("ad_group", "department"):
            warnings.append("match_type must be 'ad_group' or 'department'")
            valid = False
        if not match_value:
            warnings.append("match_value is required")
            valid = False
        if not role_id:
            warnings.append(f"Role '{role_name}' not found — create it first, then re-run")
            valid = False
        if scope_type and scope_type not in {s["id"] for s in manifest_dict.get("scope_types", [])}:
            warnings.append(f"Unknown scope_type '{scope_type}'")
            valid = False
        if scope_type and not scope_id:
            warnings.append(f"scope_type '{scope_type}' set but no scope_id — LLM couldn't find a matching resource")
            valid = False
        who = (
            f"everyone in AD group {match_value!r}" if match_type == "ad_group"
            else f"users in department {match_value!r}"
        )
        where = f" in {scope_type}={scope_id}" if scope_id else " tenant-wide"
        summary = f"Auto-assign {role_name!r} to {who}{where}"
        return ProposedAction(
            kind="create_mapping",
            body={
                "match_type": match_type,
                "match_value": match_value,
                "role_id": role_id,
                "scope_type": scope_type,
                "scope_id": scope_id,
                "notes": "Proposed by assistant",
            },
            summary=summary,
            warnings=warnings,
            valid=valid,
        )

    warnings.append(f"Unknown action kind: {kind}")
    return ProposedAction(kind=kind or "unknown", body=action, summary=f"Unknown action '{kind}'", warnings=warnings, valid=False)


# ── Entry point ─────────────────────────────────────────────────────────────


REVIEWER_SYSTEM_PROMPT = """You are a senior permissions reviewer for a
line-of-business app. A proposer agent has drafted actions to fulfill an
admin's request. Your job is to critique each proposal and produce a revised,
safer, more intent-faithful action set before the admin sees anything.

For every draft action, assign a verdict:
- "approved": safe and correct — keep as-is.
- "modified": the action is mostly right but something needs fixing. Emit
  the corrected action and explain the change in review_notes.
- "rejected": the action is wrong, unsafe, or misreads the admin's intent.
  Explain why in review_notes. The admin will see the rejection.
- "added": the proposer missed an action required to fulfill the request
  (e.g. the admin asked for read-all + edit-HR and the proposer only gave
  the edit action — you'd add the read-all).

Apply this review checklist to EVERY action before approving it:

0. FIX VALIDATOR WARNINGS FIRST. Each proposer action carries a
   `_validator_warnings` list. If that list is non-empty, the action is
   WRONG — modify it to fix every warning, or reject it. Common fixes:
     - match_type must be EXACTLY "ad_group" or "department". Never
       "owner_group", "sop", "library", or anything else. Scope type
       goes in scope_type, NOT match_type.
     - Unknown permissions must be dropped (only use ids from the catalog).
     - When scope_type is set, scope_id is required (and vice versa).
1. INTENT — does it match what the admin asked for, or just a literal
   word-by-word translation that misses the goal?
2. MINIMAL PERMISSIONS — no extra capabilities the admin didn't ask for.
3. SCOPE — prefer a library scope over tenant-wide when the admin hints
   at a specific team/department.
4. GROUP vs INDIVIDUAL — if the admin says "give HR" / "anyone in IT",
   the correct action is create_mapping, not assign_role per user.
5. REUSE — is there an existing role that already fits? Don't create
   new roles when a system role or custom role does the job.
6. SECURITY RED FLAGS:
     - admin role granted through a mapping (never auto-assign admin)
     - a mapping that grants "*" permissions
     - an assign_role that targets the same user_id as the caller
       (suspicious self-grant)
     - missing scope when the admin clearly wanted a scoped grant
7. MISSING ACTIONS — did the proposer forget one? Especially common:
     - "read all + edit one" needs TWO actions
     - "move access from X to Y" needs a revoke as well as an assign
     - a mapping that references a role the proposer didn't also create

REMINDER ON FIELD NAMES (do not confuse these):
    match_type    → "ad_group" | "department"  (how to match a user)
    match_value   → the AD group name or the department name (string)
    scope_type    → "owner_group" | "sop" | ... (what resource to scope to)
    scope_id      → the id of that scope resource

You may also append `questions` — escalate to the admin when even a
corrected set of actions would still be guessing. (If you're escalating,
include only the actions you're confident about, plus the questions.)

## Example — catching proposer confusion:

Proposer produced:
  { "kind": "create_mapping",
    "match_type": "owner_group",    ← WRONG — this is a scope type
    "match_value": "HR",
    "role_name": "library_editor",
    "_validator_warnings": ["match_type must be 'ad_group' or 'department'"] }

Your corrected action:
  { "kind": "create_mapping",
    "match_type": "ad_group",        ← FIXED
    "match_value": "HR",
    "role_name": "library_editor",
    "scope_type": "owner_group",     ← scope moved to the right field
    "scope_id": "<id of HR library>",
    "review_verdict": "modified",
    "review_notes": "Proposer put the scope type in match_type. Corrected to ad_group, moved scope to scope_type/scope_id.",
    "original_index": 0 }

You have full context: the exact permission catalog, every existing role
with its current permissions, every scope resource with its id and name.
USE THAT CONTEXT — don't invent permission ids, role names, or scope ids.

Output format: ONE JSON object:
{
  "reviewer_summary": "1–2 sentences on what you changed vs the proposer",
  "actions": [
    {
      "kind": "create_role" | "assign_role" | "create_mapping",
      ... action-specific fields (same as the proposer's format) ...,
      "review_verdict": "approved" | "modified" | "rejected" | "added",
      "review_notes": "why this verdict",
      "original_index": 0   // optional — index into proposer's actions
                            // array for modified/rejected verdicts
    }
  ]
}

If the proposer got everything right, return all actions with verdict
"approved" unchanged. If the proposer failed entirely, you can return a
wholly new action set — you're the source of truth for what the admin sees.

Do NOT include prose outside the JSON. No code fences. JSON only."""


def review_actions(
    admin_request: str,
    proposer_actions: list[dict],
    proposer_understanding: str,
    proposer_notes: str,
    context_block: str,
) -> dict | None:
    """Run the proposer's draft through a skeptical second-stage LLM.
    Returns the revised action list + summary, or None if review failed
    (caller falls back to proposer output)."""

    if not proposer_actions:
        return None

    user = f"""{context_block}

Admin request:
{admin_request}

Proposer's understanding: {proposer_understanding}

Proposer's draft actions (review each, emit revised):
{json.dumps(proposer_actions, indent=2)}

{f"Proposer notes: {proposer_notes}" if proposer_notes else ""}

Respond with JSON only, matching the schema described in the system prompt."""

    try:
        return call_ollama_json(
            REVIEWER_SYSTEM_PROMPT, user,
            model=ADMIN_REVIEWER_MODEL,
            timeout_s=ADMIN_ASSISTANT_TIMEOUT_S,
        )
    except OllamaError as e:
        logger.warning("Reviewer call failed (falling back to proposer output): %s", e)
        return None


def propose_actions(
    admin_request: str,
    manifest_dict: dict,
    roles: list[dict],
    scope_options: dict[str, list[dict]],
    app_identity: str = "",
    current_mappings: list[dict] | None = None,
    current_assignment_count: int = 0,
) -> dict:
    """Main entry point called from the router.

    Args:
        admin_request: The admin's plain-English prompt.
        manifest_dict: Output of `AppManifest` router serialization — same
            shape the UI sees from GET /admin/manifest.
        roles: Existing roles for the tenant+app (for name→id lookup).
        scope_options: { scope_type_id: [{id, name}, ...] } — e.g. owner_groups.

    Returns:
        { "understanding": str, "actions": [ProposedAction.to_dict()], "notes": str,
          "model": str, "raw": dict (the LLM's original response, for debugging) }
    """
    context = _build_context_block(
        manifest_dict, roles, scope_options,
        app_identity=app_identity,
        current_mappings=current_mappings,
        current_assignment_count=current_assignment_count,
    )
    user_prompt = build_user_prompt(context, admin_request)
    try:
        raw = call_ollama_json(
            SYSTEM_PROMPT, user_prompt,
            model=ADMIN_ASSISTANT_MODEL,
            timeout_s=ADMIN_ASSISTANT_TIMEOUT_S,
        )
    except OllamaError as e:
        return {
            "understanding": "",
            "actions": [],
            "questions": [],
            "notes": "",
            "error": str(e),
            "model": ADMIN_ASSISTANT_MODEL,
            "raw": None,
        }

    understanding = str(raw.get("understanding") or "")
    notes = str(raw.get("notes") or "")
    proposer_questions = raw.get("questions") or []
    if not isinstance(proposer_questions, list):
        proposer_questions = []
    raw_proposer_actions = raw.get("actions") or []
    if not isinstance(raw_proposer_actions, list):
        raw_proposer_actions = []

    # Pre-validate proposer actions so the reviewer sees concrete warnings
    # ("match_type must be 'ad_group' or 'department'") rather than having
    # to re-derive them from the schema rules.
    proposer_validated_payloads = []
    for a in raw_proposer_actions:
        pa = validate_action(a, manifest_dict, roles)
        proposer_validated_payloads.append({
            **a,
            "_validator_warnings": pa.warnings,
            "_validator_valid": pa.valid,
        })

    # ── Stage 2: reviewer agent critiques the proposer's draft ──────────
    reviewer_summary = ""
    reviewer_ran = False
    reviewer_questions: list[str] = []
    if ADMIN_REVIEWER_ENABLED and raw_proposer_actions:
        reviewer_raw = review_actions(
            admin_request=admin_request,
            proposer_actions=proposer_validated_payloads,
            proposer_understanding=understanding,
            proposer_notes=notes,
            context_block=context,
        )
        if reviewer_raw is not None:
            reviewer_ran = True
            reviewer_summary = str(reviewer_raw.get("reviewer_summary") or "")
            rq = reviewer_raw.get("questions") or []
            if isinstance(rq, list):
                reviewer_questions = [str(q) for q in rq]
            revised = reviewer_raw.get("actions") or []
            if not isinstance(revised, list):
                revised = []
            actions = [
                _merge_review(a, raw_proposer_actions, manifest_dict, roles).to_dict()
                for a in revised
            ]
        else:
            # Review failed — fall back to proposer output, unannotated.
            actions = [
                validate_action(a, manifest_dict, roles).to_dict()
                for a in raw_proposer_actions
            ]
    else:
        actions = [
            validate_action(a, manifest_dict, roles).to_dict()
            for a in raw_proposer_actions
        ]

    # Merge questions from both agents, de-duplicated, preserving order.
    questions: list[str] = []
    seen = set()
    for q in list(proposer_questions) + list(reviewer_questions):
        q = str(q).strip()
        if q and q not in seen:
            seen.add(q)
            questions.append(q)

    return {
        "understanding": understanding,
        "actions": actions,
        "questions": questions,
        "notes": notes,
        "reviewer_summary": reviewer_summary,
        "reviewer_ran": reviewer_ran,
        "model": ADMIN_ASSISTANT_MODEL,
        "reviewer_model": ADMIN_REVIEWER_MODEL if reviewer_ran else None,
        "raw": raw,
    }


def _merge_review(
    revised_action: dict,
    proposer_actions: list[dict],
    manifest_dict: dict,
    roles: list[dict],
) -> ProposedAction:
    """Turn one reviewer-emitted action (with verdict/notes) into a
    validated ProposedAction. If verdict is modified/rejected, attach the
    proposer's original body so the UI can render a diff/disclosure."""
    verdict = revised_action.get("review_verdict", "approved")
    notes = str(revised_action.get("review_notes") or "")
    original_index = revised_action.get("original_index")

    # Strip review meta from the action dict before passing to validator
    # (validator expects the plain action schema).
    clean_action = {k: v for k, v in revised_action.items()
                    if k not in ("review_verdict", "review_notes", "original_index")}
    validated = validate_action(clean_action, manifest_dict, roles)
    validated.review_verdict = verdict if verdict in ("approved", "modified", "rejected", "added") else "approved"
    validated.review_notes = notes

    # Attach the proposer's original when the reviewer changed or killed it.
    if verdict in ("modified", "rejected") and isinstance(original_index, int) \
       and 0 <= original_index < len(proposer_actions):
        original = proposer_actions[original_index]
        validated.original_body = original
        orig_validated = validate_action(original, manifest_dict, roles)
        validated.original_summary = orig_validated.summary

    # Rejected actions are never appliable, regardless of what validator said.
    if verdict == "rejected":
        validated.valid = False

    return validated
