# Cold Case

Cold case investigation, lead management, and evidence tracking for law enforcement

## Stack

| Concern | Version |
|---|---|
| Frontend | React 19 · Vite 7 · Tailwind 4 · @tanstack/react-query 5 · axios 1 · TypeScript 5.7 |
| Backend | FastAPI 0.115 · MongoEngine 0.29 · Python 3.12+ · pydantic 2 · pydantic-settings 2 |
| Database | MongoDB 7 |
| LLM (local) | Ollama · default text model `qwen3.6:35b-a3b-nvfp4` |

## Ports

| Service | Default |
|---|---|
| Frontend | `5178` |
| Backend | `7787` |
| MongoDB | `27022` |

Env-driven via `.env`. See `~/Documents/Claude/knowledge/launchpad/port-allocation.md`.

## Quick start

```bash
# first run: install git hooks (one-time per clone)
./scripts/install-git-hooks.sh

# bring up stack
./dev.sh
```

Open `http://localhost:5178/`.

## Layout

See [`STRUCTURE.md`](STRUCTURE.md) for the canonical directory tree, and [`docs/architecture.md`](docs/architecture.md) for the auto-generated architecture description.

Entry points for agents: [`AGENTS.md`](AGENTS.md) (master — every IDE), [`CLAUDE.md`](CLAUDE.md) (Claude Code additions), `codex-instructions.md` (Codex), `.cursorrules` (Cursor), `.windsurfrules` (Windsurf).

## Generated from

This repo was scaffolded by [`launchpad-starter-kit v0.2.1`](~/Documents/Claude/Projects/hopkinsville/launchpad-starter-kit/). Update workflow: [retrofit-existing-app.md](~/Documents/Claude/knowledge/launchpad/retrofit-existing-app.md).
