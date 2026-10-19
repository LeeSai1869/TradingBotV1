# ============================================================
# live_runner.py
# Thin wrapper around Global Core orchestrator.
# Kept for backward compatibility.
# ============================================================

from __future__ import annotations

import sys

from Section_1_Global_Core.orchestrator import (
    GlobalCoreOrchestrator,
    DEFAULT_POLL_SECONDS,
)


def main():
    orch = GlobalCoreOrchestrator(poll_seconds=DEFAULT_POLL_SECONDS)
    orch.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
