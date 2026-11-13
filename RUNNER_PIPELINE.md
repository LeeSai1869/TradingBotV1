# Runner priority and catch-up

The normal three-processor runner uses bounded turns on startup and every cycle:

1. Refresh recent closed candles for existing coins, without downloading bulk history in that turn.
2. Advance small current-generation feature tails, including the bulk owner's other timeframes, before any bulk work. The recent turn has a half-second budget, at most 64 pairs and 12 rows per pair. It never skips the downloaded historical prefix, admits a pending selective repair, or resets a checkpoint.
3. Select ready symbol/timeframe pairs from their committed feature checkpoint, formula signature and repair state. Run Section 5 live publications and historical classifications for those exact pairs. A pending coin or timeframe does not block another pair; individual engines retain their dependency and generation checks. Lack of a fresh network candle does not prevent processing already committed stored inputs.
4. Run BUY/SELL maintenance for feature-ready pairs. Section 5 historical completion is not a prerequisite for the DI decision worker. The event path uses the same pair readiness and rechecks it after bulk feature work.
5. Give existing bulk candle history and chronological/selective feature replay separate half-second turns. Then use idle capacity to initialize one new coin at a time. Promote it only after full candle and feature history are complete.

An existing coin has a committed feature checkpoint at first deployment. The cohort is persisted in runner state (`__pipeline_existing__`), so a partly initialized new coin does not become existing after restart. Paused symbols/timeframes do not participate. First-close waits do not create artificial history work.

New candles, feature generation changes, raw epochs and engine producer changes invalidate cached analytical completion flags. Live publications and historical classifications retain separate runs. Explicit pair filters avoid accidentally including blocked symbol/timeframe combinations through a Cartesian product. A waiting analytical scope does not gate decisions or another pair's analytical progress.

These are soft deadlines checked between batches: an individual database transaction or network request can overrun. Recent downloads and feature work receive another turn next cycle before bulk history. No extra process competes for the writer. All analytical inputs come from stored data.

BUY/SELL formulas, alternating signal rules, feature formulas, and targeted feature repair semantics are unchanged. The recent lane uses the same chronological feature writer; pending selective recalculations remain on their existing resumable replay path. No source data is deleted or reset.

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
