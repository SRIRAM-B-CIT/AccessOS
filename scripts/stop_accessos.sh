#!/usr/bin/env bash
# ============================================================
# AccessOS Stop Script
# Sends SIGTERM to any running accessos process.
# ============================================================
set -euo pipefail

PIDS=$(pgrep -f "python3 -m accessos" 2>/dev/null || true)

if [[ -z "$PIDS" ]]; then
    echo "AccessOS is not running."
    exit 0
fi

echo "Stopping AccessOS (PIDs: $PIDS)"
kill -SIGTERM $PIDS
sleep 1

# Check if still running
REMAINING=$(pgrep -f "python3 -m accessos" 2>/dev/null || true)
if [[ -n "$REMAINING" ]]; then
    echo "WARNING: Process still running; sending SIGKILL"
    kill -SIGKILL $REMAINING
fi

echo "AccessOS stopped."
