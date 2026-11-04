#!/bin/bash
set -e
cd "$(dirname "$0")/../../.."
exec "${TRADINGBOT_PYTHON:-python3}" -u -m Section_1_Global_Core.memory_storage.Runner.live_runner
