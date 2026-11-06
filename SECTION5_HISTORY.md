# Section 5 live and historical calculation

The normal runner now services two explicitly separate lanes for enabled symbols
and registered active timeframes:

- Live: retains the existing recent 32-candle seed and advances toward new closes.
  Existing current publications, MTF aggregation and decision gates retain their
  live path.
- History: starts at the earliest stored candle (`since=0`), resumes versioned
  checkpoints and writes classifications to the same intelligence memory under
  separate run identities. It does not replace live bindings with old results.

Previously only the first lane ran automatically. Reducing the active coin count
could not make that recent seed process earlier years. A current engine result
therefore did not establish complete historical classification coverage.

## Deployment and progress

```sh
git pull --ff-only origin main &&
python3 restart_runner.py &&
python3 intelligence_status.py --summary --output intelligence_readiness.json
```

The command's first summary describes live readiness. The second describes
full-history coverage, with classified and pending candles per engine and the
number of scopes without a usable target. Per-symbol/timeframe detail is in each
engine's `history` object in the JSON: first/through timestamps, feature checkpoint,
latest closed candle, pending count and checkpoint reason.

With no symbol/timeframe arguments the command lists the runner's actual active
data-policy scopes. These can differ from coins merely selected or visible in a
chart. Check this list when expecting only four active coins.

Run the status command again after a few minutes to check progress. Runner logs
use `[history:regime]`, `[history:trend]`, etc. Restarting resumes committed runs;
it does not restart them from zero. Old engine generations remain identifiable.
Paused coins/timeframes receive no historical turns.

`CAUGHT_UP` means classified through the latest stored closed candle with compatible
feature metadata and no pending feature repair. It does not establish predictive
performance or full external-data coverage. `BACKFILLING`,
`WAITING_FOR_FEATURE_CHECKPOINT`, `FEATURE_REPLAY_PENDING`, outdated-generation
states and explicit adapter/dependency waits identify different causes of missing
history. Targets refer to stored candles, not proof that exchange ingestion is
current. Consult the live readiness/market-data diagnostics for that separately.

## Boundaries and budgets

The history scheduler uses bounded turns after live analytical maintenance. Defaults
are 200 rows and a 0.5-second soft budget, with at most four scope visits per
history turn; each call requests at most 100 rows including nested dependency work.
The existing live budget remains separate. These are soft deadlines checked
between calls, not interruption of a running SQLite transaction or evaluation.
The runner remains one process; this is not a second unbounded background writer.
History adds bounded work and disk usage, so completion time depends on actual
candle volume and other workloads, not just the count of active coins. No two-day
completion guarantee is made.

Trend/Phase reuse their existing versioned dependency contracts. Historical Bias
joins the separately indexed historical runs for all nine dependencies, rather
than accidentally starting at their recent live seeds. The new
`engine_history_bindings` table indexes these runs; existing `mtf_bindings` remain
the live publication index. Changes in the Bias input adapter create a new Bias
producer lineage; previous Bias records remain. No Section 4 formulas, feature
checkpoints, BUY/SELL rules, confidence weights or app UI are changed.

Research readers may use the indexed compatible historical run when its committed
cursor is at least as current as the selected live run. An unfinished old prefix
does not replace a more recent selected live run. Where no usable live binding
exists, research may expose the committed historical prefix, with its status and
coverage. Research exports remain snapshots; regenerate them after history fills.

Historical book/news/social observations remain unavailable if they were never
recorded. Their absence cannot be repaired by candle replay. Classifications
reproduce the current analytical implementations; operational completion does not
validate the mathematical quality of those implementations.

## Verification

`python3 -m unittest discover -s tests -p 'test_analytical*.py'` covers all ten
engines on isolated SQLite histories, restart continuation, distinct recent/full
run identities, Bias dependency lineage, unchanged live bindings/raw/features,
pause/version guards, feature waits and bounded scheduling. Related Bias,
intelligence-readiness and research-reader tests protect existing consumers.
