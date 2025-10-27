#!/usr/bin/env bash
# Helper to run manage.py inside the project's virtualenv without interactive activation.
# Usage: ./scripts/run_manage.sh migrate

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$ROOT_DIR/venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  echo "Virtualenv python not found at $VENV_PY"
  echo "If your venv is elsewhere, set VENV_PY to the venv python path or update this script."
  exit 1
fi

# Execute manage.py with provided arguments
"$VENV_PY" "$ROOT_DIR/manage.py" "$@"
