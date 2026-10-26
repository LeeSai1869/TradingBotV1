# ============================================================
# live_runner.py
# Thin wrapper around Global Core orchestrator.
# Canonical login-service entrypoint.
# ============================================================

from __future__ import annotations

import faulthandler
import signal
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

from Section_1_Global_Core.orchestrator import (
    GlobalCoreOrchestrator,
    DEFAULT_POLL_SECONDS,
    _save_state,
)


def main():
    faulthandler.enable()
    if hasattr(signal,"SIGUSR1"):
        faulthandler.register(signal.SIGUSR1,all_threads=True)
    root=Path(__file__).resolve().parents[3]
    started=datetime.now(timezone.utc).isoformat()
    print(f"[runner] started={started} pid={os.getpid()} project={root} python={sys.executable}",flush=True)
    orch = GlobalCoreOrchestrator(poll_seconds=DEFAULT_POLL_SECONDS)
    orch._state['__runner__']={'pid':os.getpid(),'started':started,'project':str(root)}
    _save_state(orch._state)
    orch.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
