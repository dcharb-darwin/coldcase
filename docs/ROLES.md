# Roles — Iteration Workflow

> You won't know the real roles until you've built and tested. That's not a failure; it's the design. This doc tells you how to handle it.

## The honest truth

Every shipped Launchpad app's first manifest was wrong.

- HR Coordinator launched with 4 roles → has 6 now (added `department_manager` + `employee_liaison` after real-Jennifer conversations).
- Crew Scheduler started with 5 → ended at 7 (added `battalion_editor` + `cross_station_reader` once station-vs-battalion distinction was real).
- SOP Builder started at 5 → ended at 6 (added `cross_library_reader` after the first HR-sees-all-but-edits-one request).

Nobody got it right up front. Stop trying. Ship iteratively.

## The three-stage path

### Stage 0 — Scaffold (week 1)

`./scaffold.sh` drops a template manifest with 3 generic roles (`admin` / `contributor` / `viewer`). **Don't replace it yet.** You don't know your domain's real verbs.

What you have is enough to:
- Wire admin screen
- Test impersonation
- Check `usePermission()` gating in nav
- Demo the shape to a stakeholder

### Stage 1 — Minimal viable (weeks 2–3)

After your first real feature lands (one model + one router + UI), author `server-py/auth/app_manifest.py` with the **minimum set that describes what you actually built**:

- `admin` (locked, `permissions=["*"]`)
- One user role (e.g. `editor` / `hr_editor` / `scheduler` — pick your domain's noun)
- One read-only role (e.g. `viewer` / `reader` / `auditor`)

That's three roles. Cover 80% of usage. Leave everything else unwritten.

**What not to do at Stage 1:**
- Guess at scoped roles ("I'll add `department_manager` just in case" — if nobody's asked for a department scope, it's noise).
- Author every permission for every router you might build.
- Create separate roles for every possible persona.

### Stage 2 — Demo + discover (weeks 3–8)

Show the app to real users. Listen for these patterns:

| What they say | What you add |
|---|---|
| "Jennifer needs to see Operations but only edit HR" | A new role + a scope type (`department`). Formalize with the admin assistant. |
| "Approvers can approve but not edit drafts" | A new role with a subset of permissions you already have. |
| "Compliance needs to see everything but never change anything" | An `auditor` role + an `audit.read` permission (usually added in the same PR). |
| "External reviewer, single SOP only" | Scope the existing `reader` role to that resource id. No new role. |
| "IT needs to be able to delete anything" | Reuse `admin` or create `super_editor` — depends on whether they're inside your permission fence. |

Use the **admin AI assistant** (`#/admin` → Assistant tab) as the translator. Tell it "give HR read-only access to Operations" and it will propose `create_role` + `assign_role` actions validated against your current manifest. Approve the proposals; it writes. This is the pattern, not an afterthought.

### Stage 3 — Formalize (demo-ready)

Before first production customer touches the app:

1. Audit your manifest. Are all perms named per `PERMISSION_CATALOG_GUIDE` conventions?
2. Are there roles nobody's been assigned to in 60 days? Delete them.
3. Is the `admin` role still `permissions=["*"]`? (It should be.)
4. Is every resource a real noun in the domain, or have you got placeholder `thing.read`?
5. Update `docs/role-evolution.md` (see below).

---

## The role-evolution log

Every Launchpad app keeps a per-app `docs/role-evolution.md` that tracks additions/refinements after Stage 1. This is NOT `agents/memory-bank/lessons.md` (which is about code mistakes). It's a **product decision log** for the manifest.

Template (put this in `docs/role-evolution.md` at scaffold time):

```markdown
# Role evolution

## 2026-05-11 — Stage 1 baseline

Initial manifest: admin + editor + viewer. 3 roles, 5 permissions.
Source: first feature slice landed in commit [...].

## YYYY-MM-DD — added <role_name>

**Why.** Real user {persona} said "...".
**Perms.** <list or diff>
**Scope.** <scope type if any>
**PR.** [trace: ...]
```

The log matters because:
- It proves decisions are customer-driven, not engineer-guessed.
- It catches "we added this 3 months ago and nobody's used it" — a signal to remove.
- It makes retrofits easy: when a similar app scaffolds later, you grep the logs across the five reference apps to find patterns.

---

## Common pitfalls

1. **Inventing permissions by router.** `employees_read / employees_list / employees_detail` all exist because you have three routes — collapse to `employee.read`. Permissions map to **capabilities**, not endpoints.
2. **Permission inflation.** If your role editor has more than ~20 checkboxes, users can't reason about it. Collapse or group.
3. **Role proliferation.** If you have 10 roles, you probably have 3 real personas + 7 scoped variants. Most of those variants should be **role + scope**, not their own role.
4. **Skipping the reviewer.** The admin assistant's two-stage proposer→reviewer is there for a reason. If you disable `ADMIN_REVIEWER_ENABLED=0`, you also skip the sanity check that catches LLM hallucinations.
5. **Using `*` for non-admin roles.** See `PERMISSION_CATALOG_GUIDE.md` §*-wildcard. Only the locked admin role uses `["*"]`.

---

## The permission catalog itself

Design the permission vocabulary carefully — it lives as long as the app does. **Before authoring your first real manifest**, read:

- **[`launchpad-admin-pattern/docs/PERMISSION_CATALOG_GUIDE.md`](../../launchpad-admin-pattern/docs/PERMISSION_CATALOG_GUIDE.md)** — naming conventions, resource/action axes, scope vs. permission distinction, when to add a verb vs. a scope. 192 lines; spend 30 minutes.

Skipping the guide means re-learning it by bad naming. Every time.

---

## Role library

Five shipped apps have proven role sets. Don't start from nothing:

- **[`ROLE-LIBRARY.md`](ROLE-LIBRARY.md)** — anonymized manifests from SOP Builder, Crew Scheduler, HR Coordinator, Redactit. Find the closest shape to your app, copy-paste as a starting point, iterate from there.

---

## See also

- [`PATTERNS.md` §2](PATTERNS.md) — Launchpad Admin Pattern architecture
- [`AGENTIC.md`](AGENTIC.md) — the proposer→reviewer that discovers roles by translating natural-language admin prompts
- [`ROLE-LIBRARY.md`](ROLE-LIBRARY.md) — proven manifests from shipped apps
- [`launchpad-admin-pattern/docs/PERMISSION_CATALOG_GUIDE.md`](../../launchpad-admin-pattern/docs/PERMISSION_CATALOG_GUIDE.md) — permission vocabulary design
- [`launchpad-admin-pattern/docs/INTEGRATION_GUIDE.md`](../../launchpad-admin-pattern/docs/INTEGRATION_GUIDE.md) — how to wire the pattern into a new app (done automatically by scaffold.sh)
