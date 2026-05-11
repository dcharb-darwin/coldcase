# Architectural Patterns

> The patterns every Launchpad app uses. Read this before adding a new module.

## 1. Provider / Adapter

**Every external system is accessed through a provider interface.** The app never calls PDS, Graph, Biz Library, or file shares directly — it calls `providers/email.py::EmailProvider` and the provider decides where to get the data.

Selection is env-driven:

```python
# core/config.py
provider_email: str = Field(default="mock")  # "mock" | "graph-api" | "smtp"
provider_calendar: str = Field(default="mock")
# ...
```

The factory in `providers/__init__.py` reads the env and returns the implementation. Mock today, real per-tenant tomorrow — **zero UI or business-logic change**.

Six providers are mandatory at scaffold time, even if unused by the current app: `employee`, `email`, `calendar`, `training`, `evaluation`, `photos`. Apps that truly don't need one can delete the file in their first commit — the goal is to make adding a provider "implement an interface" not "bolt a pattern on."

## 2. Launchpad Admin Pattern (RBAC)

Canonical source: `launchpad-admin-pattern/`.

Backend (`server-py/launchpad_admin/`):
- `middleware.py` — attaches `UserContext` to every request
- `models.py` — `Role`, `RoleAssignment`, `RoleMapping` MongoEngine docs
- `manifest.py` — `AppManifest`, `PermissionMeta`, `ScopeType`, `SeedRole` dataclasses
- `seed.py` — idempotent `seed_system_roles()`
- `router.py` — `build_admin_router(APP_MANIFEST)` → full `/admin/*` surface
- `context.py`, `decorators.py`

Frontend (`src/launchpad-admin/`):
- `UserContextProvider` — wraps the app, loads `GET /admin/me`
- `AdminShell` — 5-tab admin console (My Access / Roles / Assignments / AD Mappings / Assistant)
- `usePermission("...")`, `useAnyPermission([...])`, `useHasRole("...")` hooks
- `Can` — render-prop permission gate
- `configureAdminApi(base)` + `configureAdminHeaders(headerFn)`
- `impersonation` module + `ImpersonationBanner` (lives in `src/components/`, not the admin package)

**The only hand-authored file per app is `server-py/auth/app_manifest.py`** — defines that app's permissions, seed roles, scope types. Everything else is copied verbatim.

Every app wires this at scaffold time — not retrofitted later. Retrofit is painful (SOP Builder and Crew Scheduler both lived through it).

**Authoring the manifest is iterative, not up-front.** See [`ROLES.md`](ROLES.md) for the three-stage workflow (scaffold → minimal viable → demo-and-discover → formalize), the role-evolution log convention, and pitfalls. Before naming your first permission, read [`launchpad-admin-pattern/docs/PERMISSION_CATALOG_GUIDE.md`](../../launchpad-admin-pattern/docs/PERMISSION_CATALOG_GUIDE.md) — 30 minutes, decades of pain avoided. For proven manifests to borrow from, see [`ROLE-LIBRARY.md`](ROLE-LIBRARY.md).

## 3. Ollama JSON mode for structured outputs

Every call to a local LLM that produces structured data uses `format: "json"` and the shared helper.

```python
from services.ollama_client import call_ollama_json

result = call_ollama_json(
    messages=[{"role": "system", "content": "..."}, {"role": "user", "content": prompt}],
    model=ADMIN_ASSISTANT_MODEL,
    temperature=0.1,
)
# result is dict parsed from JSON response — raises OllamaError on transport/parse failure
```

Never re-roll the HTTP call. Never call without JSON mode for structured output — higher temperature causes parse failures, and a stringly-typed response goes straight to a validator that will reject it.

See `services/ollama_client.py` in the template.

## 4. Proposer → Reviewer (two-stage AI)

High-stakes AI actions (permission changes, scheduler recommendations) run through two model calls:

1. **Proposer** drafts a set of structured proposed actions.
2. **Reviewer** receives the proposer's output + full app context, then critiques / modifies / rejects.

Both verdicts render in the UI; the user sees what the proposer said, what the reviewer changed, and applies per-action. See `services/admin_assistant.py` for the reference implementation.

Default: same model for both (`ADMIN_ASSISTANT_MODEL`). Override `ADMIN_REVIEWER_MODEL` to a stronger model for stricter review.

## 5. Audit — fire and forget

Every HR / admin / operational mutation calls `services/audit.py::record(...)`. The helper **never raises** — Mongo write failures log and return, because an audit-write blowup must not break the caller.

```python
from services.audit import AuditAction, EntityType, record as audit_record

audit_record(
    actor_id=DEV_USER_ID,
    action=AuditAction.TASK_STATUS_CHANGE,
    entity_type=EntityType.ONBOARDING_TASK,
    entity_id=str(task.id),
    message=f"Task '{task.task_name}': {old_status} → {new_status}",
)
```

Audit is append-only. Retention is per-app policy (see `docs/branding.md` or equivalent).

## 6. Env-driven ports (durable rule)

Every port — backend, mongo host-mapped, frontend dev — is read from `.env`. Never hard-code in `docker-compose.yml`, `vite.config.ts`, or application code. See `knowledge/launchpad/port-allocation.md` in the Darwin knowledge vault for the registry.

Kit default placeholders (substituted by `scaffold.sh`): `BACKEND_PORT`, `MONGO_PORT`, `FRONTEND_PORT`.

## 7. Named Mongo volume per app

`docker-compose.yml` declares the volume with an app-prefixed name:

```yaml
volumes:
  mongo_data:
    name: coldcase_mongo_data
```

Anonymous volumes orphan on `docker rm`. Named volumes survive `docker compose down` cleanly and can be backed up by name.

## 8. Feature-scoped frontend

Frontend features live at `src/features/<feature>/` with the shape:

```
src/features/<feature>/
├── pages/         ← route-level components
├── components/    ← feature-private UI
├── hooks.ts       ← view-model hooks
├── types.ts       ← feature-local contracts
└── index.ts       ← barrel export
```

Cross-feature hooks go to `src/lib/` (data hooks, query keys). Cross-feature components go to `src/components/` (Darwin primitives).

## 9. Hash routing (POC default)

Launchpad apps default to hash routing (`window.location.hash`). Simpler than a router library for single-tree apps; reverse proxies don't need rewrite rules. Routes centralized in `src/shell/routes.ts`; route guards via `is<Page>Route(path)` helpers.

Apps that outgrow hash routing migrate to `react-router` or `@tanstack/router` as a discrete task — not a day-one concern.

## 10. Architecture diagram SOP

Every app ships `docs/architecture.md` (auto-generated by the `architecture-diff-gate` skill) and a `docs/architecture.html` rendered from it by the `architecture-diagram` skill. A tracked `.githooks/pre-push` reminds the developer when architecture-relevant files change.

See `knowledge/launchpad/architecture-diagram-sop.md` in the vault.

## 11. Commit trailers

Every feat/fix/chore commit ends with `[trace: <slug>]`. Slug is `<app-short>-<concern>` — e.g. `rtchr-alerts`, `sop-qwen-default`, `kit-bootstrap`. Git identity for Launchpad work: `dcharb-darwin <daniel.charboneau@darwingov.com>`.

## 12. 500-line file cap

Python and TypeScript files are capped at 500 lines. At the cap, refactor into modules. This is a hygiene rule, not a hard lint — but it's a reliable signal that a file is doing too much.

## Patterns that are NOT in this doc

- Testing patterns → `CONVENTIONS.md`
- Naming + style → `CONVENTIONS.md`
- Design system visuals → `PRINCIPLES.md` §P5 (tokens)
- Agentic UX rules → `PRINCIPLES.md` part 2
- AI assistant implementation → `AGENTIC.md`
