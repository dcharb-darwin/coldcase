#!/bin/sh
# scripts/install-git-hooks.sh
#
# Wires this repo's tracked .githooks/ directory into git's hook path.
# One-time setup per clone. Idempotent.
#
# Managed by the `architecture-diff-gate` skill.
# See: ~/Documents/Claude/knowledge/launchpad/architecture-diagram-sop.md

set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

if [ ! -d .githooks ]; then
  echo "error: .githooks/ directory missing. Something is wrong with the repo state." >&2
  exit 1
fi

# Make hook scripts executable (git doesn't preserve +x on some checkouts).
chmod +x .githooks/* 2>/dev/null || true

# Point git at our tracked hooks.
git config --local core.hooksPath .githooks

echo "✓ Git hooks installed (core.hooksPath = .githooks)"
echo "  Hooks active:"
ls -1 .githooks/ | sed 's/^/    /'
