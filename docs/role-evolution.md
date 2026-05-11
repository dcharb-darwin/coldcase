# Role evolution — Cold Case

> Product-decision log for `server-py/auth/app_manifest.py` (permissions, seed roles, scope types).
> NOT the same as `agents/memory-bank/lessons.md` (code mistakes). This file is about **why** the role set looks the way it does.

## 2026-05-11 — Stage 0 scaffold

Initial template manifest from `launchpad-starter-kit v0.2.1`:
- `app_id=your_app` (placeholder — must be replaced before first commit of real code)
- 7 generic permissions (`thing.read/create/edit_own/edit_any/delete` + `admin.view` + `roles.manage`)
- 3 seed roles: `admin` (locked, `["*"]`), `contributor`, `viewer`

**Action required:** replace the placeholder with Stage 1 minimal-viable manifest before the first feature lands. See [`./ROLES.md`](./ROLES.md#stage-1--minimal-viable-weeks-23).

## Template entry (delete once you have real ones)

### YYYY-MM-DD — added `<role_name>`

**Why.** Real user / persona said "...".
**Perms granted.** `<list>` (or "+3 to existing").
**Scope.** `<scope_type>` (or "tenant-wide").
**How authored.** Admin assistant proposer+reviewer (session X) / direct manifest edit.
**Commit.** `[trace: coldcase-role-<slug>]`
**Validation.** Assigned to <user/group>; confirmed they can do X and cannot do Y.

---

## When to prune

Review this file every 60 days. If a role has zero assignments over that window and isn't an intentional reserve (e.g. external-auditor role used at audit time), delete it in the next manifest edit. Log the deletion as its own entry.
