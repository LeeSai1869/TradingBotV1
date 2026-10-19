# ============================================================
# tools/freeze_check.py
# One-shot verifier: confirms Global Core is in a valid state.
# ============================================================
#
# Run before any session that touches Global Core.
# If it fails, do NOT modify Global Core — fix the failure first.
#
# Checks:
#   1. Freeze record exists in GLOBAL_CORE_README.md
#   2. symbols.json loads, passes validation, matches expected counts
#   3. Audit A1 + A2 + A5 pass on current data
#   4. Orchestrator module imports cleanly
#   5. No NEW public-surface violations
# ============================================================

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GLOBAL_CORE = PROJECT_ROOT / "Section_1_Global_Core"


def _ok(msg):
    print("  [OK]  " + msg)


def _fail(msg):
    print("  [FAIL] " + msg)


def check_freeze_record() -> bool:
    print("[1] freeze record in GLOBAL_CORE_README.md")
    readme = GLOBAL_CORE / "GLOBAL_CORE_README.md"
    if not readme.exists():
        _fail("README missing")
        return False
    text = readme.read_text(encoding="utf-8")
    if "Locked: 2026-" not in text:
        _fail("no Locked: YYYY-MM-DD line")
        return False
    m = re.search(r"Locked: (\S+)", text)
    _ok("locked at " + m.group(1))
    return True


def check_symbols() -> bool:
    print("[2] symbols.json")
    try:
        from Section_1_Global_Core.Symbols import symbols as s
        approved = s.get_approved_symbols()
        staged = s.get_staged_symbols()
        cap = s.get_active_cap()
        _ok(f"approved={len(approved)} {approved}")
        _ok(f"staged={len(staged)}")
        _ok(f"active_cap={cap}")
        if "BTCUSDT" not in approved or "SUIUSDT" not in approved:
            _fail("expected BTCUSDT and SUIUSDT in approved")
            return False
        return True
    except Exception as e:
        _fail(f"symbols load error: {e}")
        return False


def check_audit() -> bool:
    print("[3] audit A1+A2+A5 (fast)")
    try:
        from Section_1_Global_Core.memory_storage.Audit import audit_runner
        m = audit_runner.run(
            sample_rows_per_pair=100,
            continuity_refetch=False,
            include_daily=False,
        )
        a1 = m["A1"]["failed"]
        a2 = len(m["A2"])
        a5 = m["A5"]["stale_count"]
        _ok(f"A1_failed={a1}  A2_unknown={a2}  A5_stale={a5}")
        if not m["pass"]:
            _fail("audit did not pass")
            return False
        return True
    except Exception as e:
        _fail(f"audit error: {e}")
        return False


def check_orchestrator() -> bool:
    print("[4] orchestrator imports")
    try:
        from Section_1_Global_Core.orchestrator import GlobalCoreOrchestrator
        o = GlobalCoreOrchestrator(poll_seconds=0)
        _ok(f"loaded {len(o._processors)} processors")
        return True
    except Exception as e:
        _fail(f"orchestrator import error: {e}")
        return False


def check_public_surface() -> bool:
    print("[5] public surface (no NEW violations)")
    try:
        r = subprocess.run(
            [sys.executable, "-m", "Section_1_Global_Core.tools.check_imports"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if r.returncode == 0:
            _ok("no new violations")
            return True
        _fail("new violations detected (run check_imports manually)")
        tail = (r.stdout or "")[-500:]
        print(tail)
        return False
    except Exception as e:
        _fail(f"enforcer error: {e}")
        return False


def main() -> int:
    print("=" * 60)
    print("GLOBAL CORE — FREEZE CHECK")
    print("=" * 60)

    results = [
        check_freeze_record(),
        check_symbols(),
        check_audit(),
        check_orchestrator(),
        check_public_surface(),
    ]

    print()
    print("=" * 60)
    if all(results):
        print("PASS — Global Core is in a valid state.")
        return 0
    print("FAIL — do not modify Global Core until resolved.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
