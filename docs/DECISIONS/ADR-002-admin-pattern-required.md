# ADR-002: Launchpad Admin Pattern is mandatory at scaffold time

- **Status:** Accepted
- **Date:** 2026-04-20

## Decision

Every Launchpad app scaffolded by `./scaffold.sh` wires the Launchpad Admin Pattern (backend `launchpad_admin/` package + frontend `launchpad-admin/` package + `auth/app_manifest.py`) on day one. There is no `--no-admin-pattern` flag.

## Context

SOP Builder adopted the admin pattern retroactively. Crew Scheduler adopted it retroactively. Both retrofits were multi-commit efforts that touched app factory, middleware, router mount order, axios interceptors, main.tsx wiring, nav gating, and session state. HR Coordinator adopted it retroactively — same pattern.

The retrofit is painful because RBAC assumptions leak into the codebase before the pattern lands: routes written without permission decorators, frontend nav written without `usePermission`, API clients written without the impersonation header. Retrofitting means revisiting every file that made one of those assumptions.

Apps that truly don't need RBAC (rare) can delete the admin pattern files in their first commit after scaffold. Apps that need it (overwhelmingly the majority) start with it wired.

## Consequences

**Positive:** no retrofit debt on new apps. Frontend and backend wiring is correct from commit 1. RBAC-aware patterns (nav gating, permission-gated routes, impersonation) compose naturally.

**Negative:** apps that don't need RBAC carry ~30 files of admin-pattern code. Smallest Launchpad app is not as small as it could be. Deletion path exists but requires confident familiarity with the pattern.

## Alternatives considered

- **Optional flag (`--with-admin-pattern`).** Rejected — developers in a hurry default to off; the fraction of apps that "didn't need it" later needed it and paid the retrofit cost.
- **Separate repos for RBAC vs non-RBAC apps.** Rejected — splits the ecosystem; most apps sit in the middle (RBAC eventually, not on day one).

## Revisit if

- A meaningful pattern of "admin-pattern deleted in first commit, app shipped fine" emerges. Then offer the opt-out.
- The admin pattern changes shape (e.g., a new RBAC backend) such that every app needs a migration anyway.
