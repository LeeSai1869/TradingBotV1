# Runner priority and catch-up

The normal three-processor runner now uses this hierarchy on startup and every cycle:

1. Refresh current candles for existing coins, then advance their missing download history.
2. Resume existing coins' feature history and selective repair jobs from committed checkpoints.
3. Once all active existing source/feature pairs are ready, process Section 5 live publications and full historical classifications, respecting engine dependencies.
4. Once all Section 5 scopes report completion for the current source prefix and producer generation, resume BUY/SELL decisions.
5. When established work is caught up, initialize one new coin at a time. Promote it after candle and feature history are complete.

An existing coin is one with a committed feature checkpoint at first deployment. The cohort is then persisted in runner state (`__pipeline_existing__`), so a partly initialized new coin does not become an existing coin after restart. Paused symbols/timeframes do not enter the barriers. A timeframe awaiting its first ever closed candle has no classification work until it closes.

This is a strict existing-universe barrier, as requested: a missing download, feature repair or blocked Section 5 dependency can defer subsequent stages across the existing universe. Logs identify the active stage, pending source pairs, unfinished analytical scopes and classification rows per turn. Existing per-engine logs show dependency/writer waits. New candles, feature generation changes, raw epochs and engine producer changes invalidate prior completion flags. No source data is deleted or reset by this scheduler.

The old historical analytical allocation was 200 rows and four scope visits per cycle. The hierarchical turn allows repeated fair rotations within three seconds, up to 100,000 rows / 10,000 visits; each engine transaction still uses at most 100 rows. Live publications have a separate half-second turn. Pending feature history receives up to three seconds. These are soft deadlines checked between batches; an individual database transaction or network request can overrun. Downloads run again on the next cycle; no extra process competes for the writer. All analytical inputs come from stored data.

BUY/SELL formulas, alternating signal rules, feature formulas, historical/live run isolation and targeted feature repair semantics are unchanged. Scheduling deliberately delays decisions while upstream work remains incomplete. The event path uses the same decision barrier.

## Deploy on macOS

From the existing checkout and activated virtual environment:

```sh
git pull --ff-only origin main
python3 -m pip install -r requirements-runtime.txt
python3 restart_runner.py
python3 intelligence_status.py --symbols BTCUSDT --intervals 1h --summary
python3 check_coin.py BTCUSDT --logs
```

The previous restart failed because `.venv-build` lacked pandas. Restart preflight still runs before stopping the old runner, and now prints a dependency installation command on failure. A UI restart is unnecessary for this scheduler change. Production throughput must be measured after this runner is restarted; tests use disposable databases.
