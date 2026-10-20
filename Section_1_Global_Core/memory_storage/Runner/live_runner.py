# ============================================================
# live_runner.py
# Thin wrapper around Global Core orchestrator.
# Kept for backward compatibility.
# ============================================================

from __future__ import annotations

import sys
import os
from pathlib import Path
from datetime import datetime, timezone

from Section_1_Global_Core.orchestrator import (
    GlobalCoreOrchestrator,
    DEFAULT_POLL_SECONDS,
)


def main():
    root=Path(__file__).resolve().parents[3]
    print(f"[runner] started={datetime.now(timezone.utc).isoformat()} pid={os.getpid()} project={root} python={sys.executable}",flush=True)
    orch = GlobalCoreOrchestrator(poll_seconds=DEFAULT_POLL_SECONDS)
    orch.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
