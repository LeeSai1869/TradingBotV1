# ATR slope storage retirement

Scope: `ema50_slope_atr`, `ema200_slope_atr`, `ema300_slope_atr`.

All three are `(EMA_now - EMA_k_bars_ago) / ATR_now`, with the exact
`measurementSlopeLength` bound to the full shared-measurement configuration hash.
The provider recognizes shipped defaults, the current validated configuration,
and exact configurations saved in `feature_atr_slope_configs`. Each saved full
configuration is validated against its fingerprint before its lookback is used.
Other historical configurations retain their stored values.

The readers reconstruct from retained EMAs, current ATR and raw candle history.
They require matching formula/shared versions, configuration identity, contiguous
candle boundaries and consistent measurement warmup counters. Calendar-month
boundaries use actual candle close times rather than a fixed-duration approximation.
Missing EMAs reset that EMA's slope window. Invalid current ATR suppresses slopes
without discarding the EMA history. Missing/invalid close resets all windows.
Missing source history or provenance falls back to the original stored field.

Normal Core reads, targeted replay prerequisites, Trend snapshots and dynamic
research SQL share the provider. It uses the caller's connection/snapshot; no
recursive EMA calculation or exchange request occurs. `read_expression` callers
opening raw SQLite connections must register `atr_slope_reads.install(conn)`.
The standard store and analytical gateways do this automatically.

## Write policy

Normal and selective writers first persist retained inputs and calculated
outputs. In that same transaction they save the actual shared configuration,
compare populated slopes with reconstructed values, then clear only equal,
reconstructible fields. A mismatch rolls back the batch and checkpoint.
Unavailable source windows keep their original stored values. Settings changes
do not erase archived configuration mappings. Indicator calculations and
checkpoints remain unchanged; physical columns remain for legacy fallback.

## Historical cleanup

After pulling the code, restart both the chart backend and live runner so all
readers and writers use the registry and policy. Wait for new committed rows.

```
python3 check_atr_slope_readers.py
python3 retire_atr_slope_storage.py --dry-run --latest
python3 -u retire_atr_slope_storage.py --apply
python3 retire_atr_slope_storage.py --status
```

The default mode is a bounded read-only dry run. `--apply` checks recent writer
output, captures a maximum rowid, and clears history in small coordinated batches.
Every populated candidate is compared again under the writer lock. Missing
metadata, unknown configurations and incomplete history retain their values.
Progress and clears commit atomically in `feature_storage_retirements`, with a
JSON mirror at `atr_slope_retirement.json`. Interrupting and rerunning the same
command resumes the committed cursor. Database replacement stops stale jobs.
`--status` reads the committed progress immediately without a full-history scan.
No candle, EMA, ATR or engine checkpoint is deleted. No vacuum/rebuild is run.
The check command also verifies omitted values can still be reconstructed.

The preceding local historical audit reported 28,267,466 compared rows with no
mismatches, 1,996 unverified prefix rows and 3,106,210 rows without shared version/
configuration metadata. Those unresolved rows are not approved for retirement.
