#!/usr/bin/env bash
# ==============================================================================
# AccessOS Stop Script (Phase 3.6 Hardened Host Safety)
# ==============================================================================
# Gracefully stops running AccessOS processes and cleans up PID locks.
# ==============================================================================
set -euo pipefail

LOCK_FILE="$HOME/.cache/accessos/accessos.pid"
PIDS=""

# 1. Check PID from lock file
if [[ -f "$LOCK_FILE" ]]; then
    FILE_PID="$(cat "$LOCK_FILE" 2>/dev/null || true)"
    if [[ -n "$FILE_PID" ]] && kill -0 "$FILE_PID" 2>/dev/null; then
        PIDS="$FILE_PID"
    fi
fi

# 2. Check any remaining accessos python processes
EXTRA_PIDS=$(pgrep -f "[p]ython.*-m accessos" 2>/dev/null || true)
if [[ -n "$EXTRA_PIDS" ]]; then
    PIDS="$(echo "$PIDS $EXTRA_PIDS" | tr ' ' '\n' | sort -u | tr '\n' ' ')"
fi

if [[ -z "${PIDS// }" ]]; then
    echo "AccessOS is not running."
    rm -f "$LOCK_FILE"
    exit 0
fi

echo "Stopping AccessOS processes (PIDs: $PIDS)..."
for pid in $PIDS; do
    if kill -0 "$pid" 2>/dev/null; then
        kill -SIGTERM "$pid" 2>/dev/null || true
    fi
done

sleep 1.5

# Check if any still alive; send SIGKILL if necessary
STILL_RUNNING=""
for pid in $PIDS; do
    if kill -0 "$pid" 2>/dev/null; then
        STILL_RUNNING="$STILL_RUNNING $pid"
    fi
done

if [[ -n "${STILL_RUNNING// }" ]]; then
    echo "Force killing stubborn processes (PIDs:$STILL_RUNNING)..."
    for pid in $STILL_RUNNING; do
        kill -SIGKILL "$pid" 2>/dev/null || true
    done
fi

rm -f "$LOCK_FILE"
echo "AccessOS stopped and lock file removed."
