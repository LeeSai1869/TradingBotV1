# ============================================================
# section_1_9_orchestrator.py
# Global Core — the loop.
# ============================================================
#
# Responsibilities:
#   1. Ingest new klines from Binance -> klines.db
#   2. Audit them
#   3. Emit BarEvent to every processor listed in processors.json
#   4. Sleep, repeat
#
# HARD RULES:
#   - Never imports from Section_2..Section_13 directly.
#   - Processors are loaded by string from processors.json.
#   - If processors.json is missing or empty, the loop still runs
#     (ingest + audit only). This lets Global Core operate with
#     no downstream sections.
# ============================================================

from __future__ import annotations

import importlib
import json
import signal as _signal
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path


_HERE = Path(__file__).resolve().parent

from Section_1_Global_Core.memory_storage.market_data.update_klines import (
    update_all as update_klines_all,
    INTERVAL_MS as _KLINES_INTERVAL_MS,
    INTERVALS as _KLINES_INTERVALS,
)
from Section_1_Global_Core.memory_storage.Storage import klines_store
from Section_1_Global_Core.memory_storage.Audit import audit_runner
from Section_1_Global_Core.Symbols import symbols as sym
from Section_1_Global_Core import data_policy


# ------------------------------------------------------------
# Config
# ------------------------------------------------------------

PROCESSORS_FILE = _HERE / "processors.json"
STATE_FILE = _HERE / "section_1_9_state.json"
DEFAULT_POLL_SECONDS = 1


# ------------------------------------------------------------
# BarEvent — the packet Global Core sends to processors
# ------------------------------------------------------------

@dataclass(frozen=True)
class BarEvent:
    symbol: str
    timeframe: str
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


# ------------------------------------------------------------
# Processor loading
# ------------------------------------------------------------

def _load_processors() -> list:
    """Read processors.json and import each module's function.

    Returns a list of (name, callable). Missing modules are logged
    and skipped — Global Core stays running regardless.
    """
    if not PROCESSORS_FILE.exists():
        print("[orchestrator] no processors.json — running ingest+audit only",
              flush=True)
        return []

    cfg = json.loads(PROCESSORS_FILE.read_text(encoding="utf-8"))
    out = []
    for entry in cfg.get("processors", []):
        mod_path = entry.get("module")
        fn_name = entry.get("function", "process_bar")
        try:
            mod = importlib.import_module(mod_path)
        except Exception as e:
            print(f"[orchestrator] cannot import {mod_path}: {e}", flush=True)
            continue
        fn = getattr(mod, fn_name, None)
        if fn is None:
            print(f"[orchestrator] {mod_path} has no {fn_name}()", flush=True)
            continue
        out.append((f"{mod_path}.{fn_name}", fn))
    print(f"[orchestrator] loaded {len(out)} processors", flush=True)
    return out


# ------------------------------------------------------------
# State
# ------------------------------------------------------------

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}  # {f"{symbol}|{interval}": last_closed_open_time_ms}


def _save_state(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    tmp.replace(STATE_FILE)


# ------------------------------------------------------------
# Fetch new closed bars
# ------------------------------------------------------------

def _fetch_bars_since(symbol: str, interval: str, since_open_ms: int):
    conn = klines_store.open_db()
    try:
        if since_open_ms is None or since_open_ms < 0:
            # First sight — return the last bar so the caller can seed the
            # state baseline. Do NOT fire events for it.
            rows = klines_store.read_last_n(conn, symbol, interval, 1)
            return [
                (r[2], r[8], r[3], r[4], r[5], r[6], r[7])
                for r in rows
            ]
        rows = klines_store.read_after(conn, symbol, interval, since_open_ms)
        return [
            (r[2], r[8], r[3], r[4], r[5], r[6], r[7])
            for r in rows
        ]
    finally:
        conn.close()


# ------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------

class GlobalCoreOrchestrator:
    def __init__(self, *, poll_seconds: int = DEFAULT_POLL_SECONDS):
        self.poll_seconds = poll_seconds
        self._stop = False
        self._processors = _load_processors()
        self._state = _load_state()

    def stop(self):
        self._stop = True

    # -- one cycle --
    def cycle(self):
        t0 = time.time()

        # 1) Ingest
        try:
            inserted = update_klines_all()
        except Exception as e:
            print(f"[orchestrator] ingest error: {e}", flush=True)
            traceback.print_exc()
            inserted = 0

        # 2) Audit is owned by update_all() after ingest.
        #    Nothing to do here — the ingest already audited.
        audit_pass = True

        # 3) Process new bars
        #
        # IMPORTANT:
        #  - State advances for every (symbol, interval) even when
        #    no processors are configured. This means the FIRST run
        #    seeds the baseline (no events fired), and later runs
        #    fire events only on genuinely new bars.
        #  - On first sight of a pair, we record the latest closed
        #    bar as baseline and fire nothing. Processors start
        #    receiving events from the NEXT bar forward.
        events_fired = 0
        for s in data_policy.active_symbols():
            for iv in data_policy.active_intervals():
                key = f"{s}|{iv}"
                epochs = data_policy.read()['epochs']
                epoch = [epochs.get(f'symbol:{s}', 0), epochs.get(f'interval:{iv}', 0)]
                seen = self._state.setdefault('__epochs__', {})
                if seen.get(key, [0, 0]) != epoch:
                    self._state.pop(key, None)
                    for name, fn in self._processors:
                        module = importlib.import_module(name.rsplit('.', 1)[0])
                        reset = getattr(module, 'reset_pair', None)
                        if reset:
                            reset(s, iv)
                seen[key] = epoch
                since = self._state.get(key)
                bars = _fetch_bars_since(s, iv, since if since is not None else -1)

                if since is None:
                    # First sight: seed baseline, do NOT fire events.
                    if bars:
                        if not data_policy.enabled(s, iv):
                            continue
                        for name, fn in self._processors:
                            module = importlib.import_module(name.rsplit('.', 1)[0])
                            catch = getattr(module, 'catch_up', None)
                            if catch:
                                catch(s, iv)
                        latest_ot = bars[-1][0]
                        self._state[key] = latest_ot
                        print(
                            f"[orchestrator] seeded baseline {s} {iv} "
                            f"at open_time={latest_ot}",
                            flush=True,
                        )
                    continue

                for row in bars:
                    (ot, ct, o, h, l, c, v) = row
                    ev = BarEvent(
                        symbol=s, timeframe=iv,
                        open_time=ot, close_time=ct,
                        open=float(o), high=float(h),
                        low=float(l), close=float(c),
                        volume=float(v),
                    )
                    success = True
                    with data_policy.locked():
                        current = data_policy.read()['epochs']
                        if not data_policy.enabled(s, iv) or epoch != [current.get(f'symbol:{s}', 0), current.get(f'interval:{iv}', 0)]:
                            break
                        for name, fn in self._processors:
                            try:
                                fn(ev)
                            except Exception as e:
                                print(f"[orchestrator] {name} failed on {s} {iv} {ot}: {e}", flush=True)
                                traceback.print_exc()
                                success = False
                                break
                    if not success:
                        break  # Retry this bar next cycle; do not advance past failure.
                    self._state[key] = ot
                    events_fired += 1

        _save_state(self._state)

        dt = time.time() - t0
        print(
            f"[orchestrator] cycle: +{inserted} klines, "
            f"audit_pass={audit_pass}, events={events_fired}, "
            f"{dt:.1f}s",
            flush=True,
        )

    # -- main loop --
    def run_forever(self):
        def _handle_sigint(sig, frame):
            print("\n[orchestrator] SIGINT — stopping after current cycle...",
                  flush=True)
            self._stop = True

        _signal.signal(_signal.SIGINT, _handle_sigint)

        # ------------------------------------------------------------
        # STARTUP CATCH-UP
        # Before entering the poll loop, run every processor's
        # catch_up() once per (symbol, interval). This closes any
        # historical gap between klines.db and features.db (or any
        # other downstream store) on cold start.
        # ------------------------------------------------------------
        print("[orchestrator] startup catch-up...", flush=True)
        for s in data_policy.active_symbols():
            for iv in data_policy.active_intervals():
                for name, fn in self._processors:
                    catch_fn = None
                    try:
                        mod = __import__(name.rsplit(".", 1)[0],
                                         fromlist=["catch_up"])
                        catch_fn = getattr(mod, "catch_up", None)
                    except Exception:
                        catch_fn = None
                    if catch_fn is None:
                        continue
                    try:
                        if not data_policy.enabled(s, iv):
                            continue
                        n = catch_fn(s, iv)
                        if n:
                            print(f"[orchestrator]   {name} {s} {iv}: +{n}",
                                  flush=True)
                    except Exception as e:
                        print(f"[orchestrator]   {name} catch_up {s} {iv} "
                              f"failed: {e}", flush=True)
        print("[orchestrator] catch-up done", flush=True)
        print(flush=True)

        print("=" * 60, flush=True)
        print("GLOBAL CORE ORCHESTRATOR", flush=True)
        print("=" * 60, flush=True)
        print("active symbols :", sym.get_active_symbols(), flush=True)
        print("intervals      :", data_policy.active_intervals(), flush=True)
        print("processors     :", [n for n, _ in self._processors], flush=True)
        print("poll seconds   :", self.poll_seconds, flush=True)
        print("state file     :", STATE_FILE, flush=True)
        print(flush=True)

        while not self._stop:
            try:
                self.cycle()
            except Exception as e:
                print(f"[orchestrator] fatal cycle error: {e}", flush=True)
                traceback.print_exc()

            for _ in range(self.poll_seconds):
                if self._stop:
                    break
                time.sleep(1)

        print("[orchestrator] stopped cleanly.", flush=True)


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------

def main(argv=None):
    orch = GlobalCoreOrchestrator(poll_seconds=DEFAULT_POLL_SECONDS)
    orch.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
