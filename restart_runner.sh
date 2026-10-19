#!/bin/bash
# ============================================================
# restart_runner.sh
# ============================================================
# Clears Python bytecode caches, then restarts the live runner
# under launchd.
#
# Use this after editing any .py file in the pipeline:
#
#     ./restart_runner.sh
#
# ============================================================

set -e

PROJECT_ROOT="/Users/jhanzeebakbar/Scalp Indicator V1"
PLIST="$HOME/Library/LaunchAgents/com.scalp.liverunner.plist"
LABEL="com.scalp.liverunner"
UID_NUM="$(id -u)"

echo "[restart] clearing __pycache__ ..."
find "$PROJECT_ROOT" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

echo "[restart] stopping launchd service ..."
launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true

sleep 1

echo "[restart] starting launchd service ..."
launchctl bootstrap "gui/$UID_NUM" "$PLIST"

sleep 1

if launchctl list | grep -q "$LABEL"; then
    echo "[restart] runner is up"
    launchctl list | grep "$LABEL"
else
    echo "[restart] WARNING: runner not found in launchctl list"
fi