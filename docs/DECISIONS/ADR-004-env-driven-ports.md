# ADR-004: Env-driven ports everywhere, no hard-coded port literals

- **Status:** Accepted (durable rule — see knowledge/launchpad/port-allocation.md)
- **Date:** 2026-04-20 (documented; rule has been in place since 2026-04-17)

## Decision

`BACKEND_PORT`, `FRONTEND_PORT`, `MONGO_PORT` live in `.env` and `.env.example`. They are the single source of truth. `docker-compose.yml`, `vite.config.ts`, `dev.sh`, `package.json` scripts all read env. No port literal appears in code except the `.env*` files.

`scaffold.sh` picks the next-available triplet from the vault registry unless overridden.

## Context

Running multiple Launchpad apps on one machine was painful: each app hardcoded `:27017` for Mongo, `:5173` for Vite, `:7774`-ish for backend. Starting a second app meant stopping the first or editing code.

The durable rule landed during Redactit (commit `redactit-env-ports`) and was retrofitted into every other app in the adoption-status table. This ADR locks it into the kit permanently.

## Consequences

**Positive:** five apps run side by side with no port surgery. Adding a sixth is a one-line registry update. Port conflicts are a config problem, not a code problem.

**Negative:** seven places to thread a port variable through (`.env`, `.env.example`, `core/config.py`, `docker-compose.yml`, `vite.config.ts`, `dev.sh`, `package.json` scripts). The generator handles it; hand-edits are tedious.

## Alternatives considered

- **One central config file (not env).** Rejected — Docker/Node/Python would each need their own reader of that file; env is the universal protocol.
- **Dynamic port allocation.** Rejected — makes URLs unpredictable for Vite proxy rules and manual curl checks.

## Revisit if

- Kubernetes / container orchestrator replaces local dev for the majority of work. Then the port assignment moves to the orchestrator and the `.env` triplet becomes a staging-time concern only.
