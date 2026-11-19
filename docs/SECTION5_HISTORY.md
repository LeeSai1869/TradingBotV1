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
python3 Section_14_Operations/services/restart_runner.py &&
python3 Section_13_Development/diagnostics/intelligence_status.py --summary --output intelligence_readiness.json
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

The history scheduler uses bounded turns after live analytical maintenance. The
analytical worker's standalone defaults reserve 200 history rows and a 0.5-second
soft budget, with at most four scope visits. The normal hierarchical pipeline
explicitly allows up to 10,000 live rows and 10,000 history rows in separate
0.5-second turns, up to 1,000 scope visits per lane; each classifier transaction
requests at most 200 rows including nested dependency work. Exhausting the live
row allowance does not subtract from the history allowance. These are soft deadlines checked
between calls, not interruption of a running SQLite transaction or evaluation.
The runner remains one process; this is not a second unbounded background writer.
History adds bounded work and disk usage, so completion time depends on actual
candle volume and other workloads, not just the count of active coins. No two-day
completion guarantee is made.

## One coin through the hierarchy

The normal pipeline now persists `__pipeline_focus__` in its existing state.
It resumes that active coin until its source/feature work, all ten compatible
historical engine cursors and decision-rule checkpoints reach their targets.
It then selects the next unfinished existing coin in configured order. Pausing
or removing the owner releases it. Recent download/feature/analytical updates
remain available to all active coins; their unfinished bulk histories do not
receive a second historical allowance. New-coin initialization waits until the
existing focus is complete.

Ready timeframes of the focus can advance immediately while another timeframe
of that coin still needs feature repair. A ready pair on another coin can still
receive live classifications and small recent decision updates. Historical
decision tails on other coins wait for their turn. Missing or incompatible
features are never bypassed just because old feature rows physically exist.

Structure feeds Trend; Trend, Structure and Participation feed Phase; all nine
base engines feed Bias. Advancing a child clears dependent cached completion
flags, so a parent cannot remain asleep at an older committed dependency prefix.
This scheduling change does not alter classifier formulas or their input/run
identities. Existing compatible histories resume rather than starting over.

Runner logs identify the bulk focus and print per-engine rows/s, calculation
time per candle, projection time and commit time for processed batches. Raw
classification speed and time spent waiting for a scheduler turn are different
measurements. No features or ADCN fields are deleted by this change.

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

`python3 -m unittest discover -s Section_13_Development/tests -p 'test_analytical*.py'` covers all ten
engines on isolated SQLite histories, restart continuation, distinct recent/full
run identities, Bias dependency lineage, unchanged live bindings/raw/features,
pause/version guards, feature waits and bounded scheduling. Related Bias,
intelligence-readiness and research-reader Section_13_Development/tests protect existing consumers.
