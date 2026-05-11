# ADR-005: Default text-reasoning LLM is `qwen3.6:35b-a3b-nvfp4`

- **Status:** Accepted (tracks vault rule — see knowledge/launchpad/ollama-models.md)
- **Date:** 2026-04-20

## Decision

Every Launchpad app scaffolded by this kit defaults `ADMIN_ASSISTANT_MODEL` + `OLLAMA_MODEL` (or equivalent) to `qwen3.6:35b-a3b-nvfp4`. Env always wins; the default is what a fresh clone sees.

The kit's version of this default tracks `~/Documents/Claude/knowledge/launchpad/ollama-models.md`.

## Context

Prior defaults (`qwen3:14b`, `llama3.1:8b`, `qwen2.5:14b`) produced slower responses and more JSON parse failures than the newer MoE (active-3B) NVFP4-quantized Qwen. SOP Builder, Crew Scheduler, HR Coordinator all bumped their defaults to `qwen3.6:35b-a3b-nvfp4` on 2026-04-20. The kit codifies that as the standard for new apps.

## Consequences

**Positive:** new apps inherit the current best default. Single place to bump when a newer model lands (this ADR + the vault doc + the kit's `templates/.env.example`).

**Negative:** if a developer doesn't have the model pulled, the admin assistant fails on first use. The kit's `USAGE.md` notes this — `ollama pull qwen3.6:35b-a3b-nvfp4` is a one-time step.

## Alternatives considered

- **Detect and fall back.** Rejected — silent fallback produces quieter bugs; explicit failure is better.
- **Bundle a model loader.** Out of scope — Ollama is assumed installed and serving on `:11434`.

## Revisit if

- A faster / smaller model lands that equals or exceeds structured-JSON reliability. Then bump the default in the vault and here.
- Ollama gains a first-class auto-pull API that makes "not installed" a non-issue.
