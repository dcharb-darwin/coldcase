# Local Development — Cold Case

App-specific local bring-up. For cross-app patterns, see `~/Documents/Claude/knowledge/launchpad/quick-start.md`.

## Prerequisites

- Docker Desktop or Docker Engine
- Python 3.12+
- Node 20+
- Ollama (for admin assistant features) — `ollama pull qwen3.6:35b-a3b-nvfp4`

## First-time setup

```bash
# 1. Clone
cd ~/Documents/Claude/Projects/hopkinsville/
git clone <repo-url> coldcase
cd coldcase

# 2. Git hooks (one-time)
./scripts/install-git-hooks.sh

# 3. Bring up
./dev.sh
```

First run triggers:
- `python3.12 -m venv .venv` + `pip install -r server-py/requirements.txt`
- `npm install`
- `docker compose up mongo -d`
- uvicorn + vite in the background

## Ports

| Service | Default | Override |
|---|---|---|
| Frontend | 5178 | `FRONTEND_PORT=...` in `.env` |
| Backend | 7787 | `BACKEND_PORT=...` |
| MongoDB | 27022 | `MONGO_PORT=...` |

## Day-to-day

```bash
# Backend only
npm run api

# Frontend only
npm run dev

# Typecheck
npm run check

# Build
npm run build

# Backend tests
cd server-py && PYTHONPATH=. ../.venv/bin/python -m unittest discover -s tests
```

## Shutdown

```bash
# Backend + frontend — whatever process IDs dev.sh printed
kill <pid1> <pid2>

# Mongo
docker stop coldcase-mongo
```

## Seed data

```bash
npm run seed       # if a seed module exists
# or
POST /launchpad/coldcase/api/phase1/seed  # if your bootstrap router is set up
```

## Reset local DB

```bash
docker stop coldcase-mongo
docker rm coldcase-mongo
docker volume rm coldcase_mongo_data
docker compose up mongo -d
# reseed
```

## Smoke check the admin pattern

```bash
curl http://localhost:7787/ready
# → {"status":"ok","service":"coldcase","mongodb":"ok"}

curl http://localhost:7787/launchpad/coldcase/api/admin/me
# → {"user_id":"dev-local-user","roles":["admin"],"permissions":[...]}
```

## Troubleshooting

- **Port already in use** → another Launchpad app is running. Check `~/Documents/Claude/knowledge/launchpad/port-allocation.md` for conflicts.
- **Mongo connection refused** → `docker start coldcase-mongo` or `docker compose up mongo -d`.
- **`ollama_client` errors** → `ollama serve` must be running; `ollama pull qwen3.6:35b-a3b-nvfp4` if the model isn't local.
- **Venv uvicorn not found** → shebang may be stale after venv move. Use `../.venv/bin/python -m uvicorn ...` instead.
