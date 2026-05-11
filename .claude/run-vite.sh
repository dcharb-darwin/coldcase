#!/usr/bin/env bash
# Wrapper to clear inherited Python env vars before launching vite,
# since the preview-tool runtime can leak a sibling project's VIRTUAL_ENV.
unset VIRTUAL_ENV
unset PYTHONHOME
unset PYTHONPATH
unset PYTHONSTARTUP
unset PYTHONUSERBASE
unset PYTHONEXECUTABLE
unset CONDA_PREFIX
exec node "$(dirname "$0")/../node_modules/vite/bin/vite.js" --host 127.0.0.1 --port 5178
