#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
exec "${TRADINGBOT_PYTHON:-python3}" -m Section_14_Operations.services.restart_runner
