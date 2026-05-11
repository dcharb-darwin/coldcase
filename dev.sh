#!/bin/bash
# Cold Case — local development startup.
#
# Brings up the full stack (mongo + backend + frontend) via docker compose.
# Ports come from .env (see knowledge/launchpad/port-allocation.md).
#
# Usage:
#   ./dev.sh              # foreground; Ctrl-C stops everything
#   ./dev.sh --build      # force-rebuild images (after a Dockerfile change)
#   ./dev.sh -d           # detached; tail logs via `docker compose logs -f`
#   ./dev.sh --reset-db   # wipe MongoDB volume and start fresh

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ ! -f .env ]; then
  echo "📝 No .env found — copying from .env.example"
  cp .env.example .env
fi

# Source .env so the echoes below show resolved values.
set -a
. "$DIR/.env"
set +a
: "${BACKEND_PORT:=7787}"
: "${FRONTEND_PORT:=5178}"
: "${MONGO_PORT:=27022}"

ARGS=()
RESET=0
DETACHED=0
for arg in "$@"; do
  case "$arg" in
    --reset-db) RESET=1 ;;
    -d|--detach|--detached) DETACHED=1 ;;
    *) ARGS+=("$arg") ;;
  esac
done

if [ "$RESET" -eq 1 ]; then
  echo "💣 Wiping MongoDB volume (coldcase_mongo_data) ..."
  docker compose down -v
fi

echo "🚀 Starting Cold Case stack via docker compose"
echo "   Frontend:  http://localhost:${FRONTEND_PORT}"
echo "   Backend:   http://localhost:${BACKEND_PORT}"
echo "   API docs:  http://localhost:${BACKEND_PORT}/docs"
echo "   Mongo:     localhost:${MONGO_PORT}"
echo ""

if [ "$DETACHED" -eq 1 ]; then
  docker compose up -d "${ARGS[@]}"
  echo ""
  echo "Tail logs:  docker compose logs -f"
  echo "Stop:       docker compose down"
else
  docker compose up "${ARGS[@]}"
fi
