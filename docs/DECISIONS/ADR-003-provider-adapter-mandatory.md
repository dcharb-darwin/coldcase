# ADR-003: Provider/Adapter pattern with six mocks is mandatory at scaffold time

- **Status:** Accepted
- **Date:** 2026-04-20

## Decision

Every scaffolded app includes six provider interfaces with mock implementations: `employee`, `email`, `calendar`, `training`, `evaluation`, `photos`. Each is env-selectable via `PROVIDER_*=mock|real-option`.

## Context

Every Launchpad app integrates with external systems that are: (a) unavailable locally, (b) organization-specific, (c) customer-specific. The provider/adapter pattern makes these swaps a configuration change instead of a code change. SOP Builder, HR Coordinator, Crew Scheduler, Redactit all use the same shape.

Pre-kit, new apps implemented providers ad-hoc. Some used the pattern; some didn't. Apps that started without it paid retrofit cost when the first customer said "can you connect to our Graph tenant?"

Apps that don't need a specific provider (a pure internal tool with no external integrations) can delete the provider file in a first commit. The bias is "have the shape" > "add the shape later."

## Consequences

**Positive:** adding a real integration never touches business logic or UI — only the provider implementation + an env flip. Customers immediately understand "we mock it today, swap when your tenant is ready."

**Negative:** six mock providers ship in every app whether they're used or not. For a truly minimal app that carries ~800 lines of unused code until deletion.

## Alternatives considered

- **Add providers as needed.** Rejected — see the retrofit cost argument.
- **Three mandatory (employee/email/calendar), three optional.** Rejected — the split is arbitrary; every app ends up needing all six within two months.
- **One generic provider interface per concern (single `Integration` class).** Rejected — typed interfaces catch integration-specific bugs that a single generic class wouldn't.

## Revisit if

- A concrete app shows that half the providers never get used in its first 6 months. Then reconsider the "delete in first commit" path as a default opt-out.
