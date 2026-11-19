# Complete the existing cleanup with verified file compaction

No new feature family is retired. The existing 24 virtual aliases and the
reviewed gap, percentage-slope, ATR-slope and EMA-distance readers stay in place.
Candle rows, retained inputs, legacy exceptions and all checkpoints remain.

The file compactor repacks existing stored records into a separate SQLite file.
It never runs the feature engine or replays indicator calculations. Physical
columns that still hold legacy values remain: dropping those would discard
preserved exceptions or require another legacy storage adapter. File compaction
can recover space from cleared cells without that additional semantic change.

```
python3 compact_feature_storage.py
caffeinate -i python3 -u compact_feature_storage.py --apply --manage-services
```

The first command is a read-only preflight. The second intentionally takes this
checkout's loaded chart and live-runner launchd services offline for the copy and
full verification. It validates both plist working directories/module arguments, including the exact
`/bin/bash <checkout>/Section_11_UI_UX/binance_chart/run_chart.sh` chart launcher,
refuses other database handles, and restarts only services that were previously
loaded, including on failure. Timeframe activation policy is never changed.

The source remains untouched during copy and verification. Sparse rowids and all
physical values are compared, auxiliary/checkpoint tables and schema objects
are checked, and SQLite quick_check must pass. A changed source or corrupt target
aborts the switch. Copy progress commits atomically with copied rows. Verification
runs again on resumption. A partial copy can resume only while the source identity,
size and modification timestamp are unchanged; resumed writer activity invalidates
it. No existing partial file, backup, or original is silently overwritten.

A smaller verified file is atomically installed; an equal/larger copy leaves the
original in place. The original is kept as `features.db.before-compaction` via a
hard link. It consumes its original space until separately removed after post-run
verification. The report is `features.db.compaction.json` beside the database.
The active file has a new inode. Completed retirement records intentionally keep
their historical source identities: do not rerun those retirements to make their
old source-match checks true. Compaction preserves them as audit evidence.

After services return, check the live quote and active charts, then run:

```
python3 check_ema_distance_readers.py
python3 check_atr_slope_readers.py
```

Live prices are independently displayed on the price-axis line and in the
status line. Stored refresh being disabled, historical navigation, a slow initial
page, or a missing stored close cannot suppress that quote. They still prevent
inserting a fictitious candle across a history gap. Provisional indicator work
has a separate executor and cannot hold up exchange price refreshes. No stale
indicator result may replace a newer quote. Unavailable feeds fall back to a
stored-price label, rather than claiming an old forming price is live.
