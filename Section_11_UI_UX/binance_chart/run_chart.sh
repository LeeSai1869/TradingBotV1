#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
echo "Starting chart server on http://localhost:8000"
echo "Press Ctrl+C to stop."
exec "${TRADINGBOT_PYTHON:-python3}" -u -m Section_11_UI_UX.server.ui_server
