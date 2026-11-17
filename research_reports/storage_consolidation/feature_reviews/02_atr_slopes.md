# ATR slope read adapters

Scope: `ema50_slope_atr`, `ema200_slope_atr`, `ema300_slope_atr`.

All three are `(EMA_now - EMA_k_bars_ago) / ATR_now`, with the exact
`measurementSlopeLength` bound to the full shared-measurement configuration hash.
The provider recognizes the shipped defaults and current validated configuration.
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

This phase changes reads only. Physical columns, stored values, writer policy,
and unresolved legacy history remain unchanged. Do not run a clearing migration
until the new readers have been checked against the actual local database.
Run `python3 check_atr_slope_readers.py` for a bounded, read-only local sample.
Before write retirement, preserve every retired configuration's hash/lookback
mapping durably; changing settings must not make a formerly reconstructible
historical configuration unknown. Current fallback remains safe because stored
ATR slopes have not been removed.

The preceding local historical audit reported 28,267,466 compared rows with no
mismatches, 1,996 unverified prefix rows and 3,106,210 rows without shared version/
configuration metadata. Those unresolved rows are not approved for retirement.
