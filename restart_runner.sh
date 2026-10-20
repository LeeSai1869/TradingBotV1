#!/bin/bash
# Run with the pipeline's Python (or use python3 restart_runner.py directly).
set -e
cd "$(dirname "$0")"
exec "${TRADINGBOT_PYTHON:-python3}" restart_runner.py
