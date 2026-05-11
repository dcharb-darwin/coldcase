# Darwin Dev Playbook

Full lifecycle for a Launchpad app — scaffold → develop → ship → hand off.

## 0. Before you start

Read:
- [`PRINCIPLES.md`](PRINCIPLES.md) — design intent
- [`PATTERNS.md`](PATTERNS.md) — architectural patterns
- [`CONVENTIONS.md`](CONVENTIONS.md) — coding conventions
- [`../knowledge/launchpad/quick-start.md`](../../../knowledge/launchpad/quick-start.md) — bring-up (in the knowledge vault)

## 1. Scaffold

```bash
cd ~/Documents/Claude/Projects/hopkinsville/launchpad-starter-kit
./scaffold.sh <slug> ~/Documents/Claude/Projects/hopkinsville/
```

Produces `~/Documents/Claude/Projects/hopkinsville/<slug>/` with:
- Full Launchpad Admin Pattern wired
- Env-driven ports (next-available triplet from vault registry)
- Architecture drift hook installed
- Seeded `docs/architecture.md`
- `git init`'d with one commit

Post-scaffold manual steps:
1. **Edit `server-py/auth/app_manifest.py`** — the only file the kit cannot write for you. Define permissions, seed roles, scope types.
2. **Update `~/Documents/Claude/knowledge/launchpad/port-allocation.md`** — add a row for your claimed triplet.
3. **Update `~/Documents/Claude/knowledge/launchpad/adoption-status.md`** — add a column for the new app.

## 2. First run

```bash
cd <slug>/
./dev.sh                   # boots mongo + backend + vite
```

Hit `http://localhost:${FRONTEND_PORT}/` and:
- Dashboard loads without errors
- `/admin` renders the admin console (dev user has admin role by default)
- `/admin/me` returns 15–17 permissions depending on manifest

If any of these fail on a fresh scaffold, it's a kit bug.

## 3. Develop

### Feature branch loop

1. Branch: `feat/<short-description>`
2. Write the PRD slice under `docs/prd/<feature>.md` (problem / data model / API / UI / acceptance / out of scope).
3. Implement backend first (model → service → router → tests).
4. Implement frontend (hooks → component → page → route → wire into shell nav).
5. Run `npm run check`, `npm run build`, backend tests. All green before commit.
6. Commit per concern: one model + its router + its tests is one commit. Backend and frontend are separate commits.
7. Trailer: `[trace: <slug>-<feature>]`.

### When architecture changes

`.githooks/pre-push` fires a yellow reminder. In your next Claude Code session, invoke `/architecture-diff-gate` — skill regenerates `docs/architecture.md` and delegates to the `architecture-diagram` skill for `docs/architecture.html`. Commit with `[trace: <slug>-architecture-refresh]`.

### When you add a new provider

1. Add the interface to `providers/base.py`.
2. Add the mock implementation to `providers/mock_<provider>.py`.
3. Add the env var to `core/config.py` (`provider_<name>: str = Field(default="mock")`).
4. Wire the factory in `providers/__init__.py`.
5. Add a row to `docs/PATTERNS.md` §1 (provider list).
6. Update the provider status panel (`routers/providers.py`) catalog.

### When permissions change

1. Edit `server-py/auth/app_manifest.py`.
2. The admin assistant's context refreshes on next call (no restart needed in dev; the middleware reloads on each request in mock mode).
3. Frontend `usePermission("...")` calls update automatically — the permissions list comes from `GET /admin/me`.
4. Document the new permission in a short note in the PRD or `branding.md` as appropriate.

## 4. Testing

- **Backend** tests live in `server-py/tests/`. Run `PYTHONPATH=. ../.venv/bin/python -m unittest discover -s tests -p "test_*.py"`.
- **Frontend** type safety is the floor: `npm run check` must pass before every commit.
- **Integration** tests hit a live Mongo via the same env-driven URL the dev server uses.
- **Browser QA** via the `browser-qa-smoke` skill for UI changes.

## 5. Ship to a preview / demo

For demo readiness:
1. Run the `generate-demo-package` workflow (`.agents/workflows/generate-demo-package.md`).
2. Seed fresh synthetic data.
3. Verify the full user journey against `docs/WALKTHROUGH.md`.
4. Generate a walkthrough script; record via the `browser-qa-smoke` skill.

## 6. Handoff

End of every Claude Code / Cowork session, run the `finalize-handover` workflow:
1. Update `SESSION_STATE.md` with commits shipped + deferred items.
2. Update `agents/memory-bank/current-state.md` if modules changed.
3. Update `docs/comprehensive-prd.md` changelog if behavior changed.
4. Run `/architecture-diff-gate` if architecture files changed.
5. Commit everything under `[trace: <slug>-session]`.

## 7. Retrofit for existing apps

If you're bringing an existing app up to this kit's conventions (not scaffolding fresh), follow `~/Documents/Claude/knowledge/launchpad/retrofit-existing-app.md` — it has the proven six-step retrofit (ports → named volume → admin pattern backend → admin pattern frontend → scaffold files → governance).

## 8. Deprecation

A feature is "deprecated" when it's still present but shouldn't be used for new work. Mark in:
- `docs/comprehensive-prd.md` changelog
- `agents/memory-bank/lessons.md` with the reason
- Code comment on the function / module pointing at the replacement

Remove deprecated code in a follow-up commit, never in the same commit as the deprecation announcement.

## 9. Emergencies

Rollback: `git revert <bad-commit>`. Never `reset --hard` on a pushed branch.

If a production app breaks after a commit, the fix is another commit, not a rewrite of history.

## 10. Rules that never bend

- No `--no-verify` on commits.
- No `--amend` on pushed commits.
- No `reset --hard` on `main`.
- No secrets in commits (`.env` is gitignored — keep it that way).
- No `any` in TypeScript.
- No hard-coded ports.
- No raw hex / rgb in component files.
- Commit trailers `[trace: <slug>]` on every feat/fix/chore.

These are the non-negotiables. Everything else is style.
