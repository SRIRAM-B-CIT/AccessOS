#!/usr/bin/env bash
# ==============================================================================
# AccessOS Launcher Script (Phase 3.6 Hardened Host Safety)
# ==============================================================================
# Usage:
#   ./scripts/run_accessos.sh                           # Host safe UI profile (default)
#   ./scripts/run_accessos.sh --profile camera-preview  # Camera preview only
#   ./scripts/run_accessos.sh --profile vm-real         # VM real injection (VM ONLY)
#   ./scripts/run_accessos.sh --windowed                # Windowed mode
#
# Guarantees:
#   1. Always executes strictly via .venv/bin/python, never system python3.
#   2. Inspects for existing instances before launching.
#   3. Defaults to host-safe mode with zero input injection.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV="$PROJECT_DIR/.venv"
VENV_PYTHON="$VENV/bin/python"

# Sanity Check 1: Dedicated virtual environment python
if [[ ! -d "$VENV" ]]; then
    echo "ERROR: Virtual environment not found at $VENV"
    echo "Create it with: python3 -m venv --system-site-packages .venv"
    exit 1
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: Virtualenv python executable not found at $VENV_PYTHON"
    echo "Recreate the virtual environment."
    exit 1
fi

# Sanity Check 2: Check for existing lock / process
LOCK_FILE="$HOME/.cache/accessos/accessos.pid"
if [[ -f "$LOCK_FILE" ]]; then
    OLD_PID="$(cat "$LOCK_FILE" 2>/dev/null || true)"
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "======================================================================"
        echo " WARNING: AccessOS appears to be already running (PID: $OLD_PID)"
        echo " Only one AccessOS instance can run at a time."
        echo " To stop the existing instance, run:"
        echo "   ./scripts/stop_accessos.sh"
        echo "======================================================================"
        exit 2
    fi
fi

# Environment defaults
export ACCESSOS_WINDOWED="${ACCESSOS_WINDOWED:-1}"
export ACCESSOS_LOG_LEVEL="${ACCESSOS_LOG_LEVEL:-INFO}"

cd "$PROJECT_DIR"

# Launch strictly through virtual environment python
exec "$VENV_PYTHON" -m accessos "$@"
