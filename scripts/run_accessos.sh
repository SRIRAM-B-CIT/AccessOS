#!/usr/bin/env bash
# ============================================================
# AccessOS Launcher Script
# ============================================================
# Usage:
#   ./scripts/run_accessos.sh           # fullscreen
#   ACCESSOS_WINDOWED=1 ./scripts/run_accessos.sh  # windowed (dev)
#
# Environment variables:
#   ACCESSOS_WINDOWED=1       run maximised instead of fullscreen
#   ACCESSOS_LOG_LEVEL=DEBUG  verbose logging
#   ACCESSOS_CONFIG=/path/...  custom settings.toml

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV="$PROJECT_DIR/.venv"

# Sanity checks
if [[ ! -d "$VENV" ]]; then
    echo "ERROR: Virtual environment not found at $VENV"
    echo "Run: python3 -m venv --system-site-packages .venv"
    exit 1
fi

if [[ ! -f "$VENV/bin/python3" ]]; then
    echo "ERROR: $VENV/bin/python3 not found"
    exit 1
fi

# Activate venv and launch
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# Default to windowed mode during development for easier iteration
export ACCESSOS_WINDOWED="${ACCESSOS_WINDOWED:-1}"
export ACCESSOS_LOG_LEVEL="${ACCESSOS_LOG_LEVEL:-INFO}"

cd "$PROJECT_DIR"
exec python3 -m accessos "$@"
