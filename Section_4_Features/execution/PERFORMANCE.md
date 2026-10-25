# Feature execution performance

The numbered feature files remain the reviewed calculation source. Imports happen
at startup, not on each candle. The pre-split/consolidated engine used the same
streaming module/function dispatch pattern. In a local cProfile run over 2,000
synthetic candles, liquidity accounted for 37% of cumulative calculation time and
volume profile 25%; the outer Engine.step body (including dispatch and exports)
accounted for about 1.5% of total time. This does not establish the cause or exact
speed of an earlier run on another machine.

`fast.py` replaces two liquidity scans and four VP reduction/value-area/node
loops with execution-only kernels. Loop ASTs and runtime/previous-value semantics
must match explicit reviewed fingerprints. Modified formulas or runtime semantics
fall back to source execution. The catalog still derives dependencies/revisions
from original statements; full and selective execution use the same optimizer.
There is no formula-version bump, new calculation column, source migration,
checkpoint reset or historical repair caused by this optimization.

Kernels preserve input order, left-first VP ties, sequential floating additions,
NA/zero handling, scratch values and persistent state. They do not smooth levels,
change lookbacks, drop features, approximate zones or batch indicators across
candles. Dynamic module helpers remain dynamic after compilation. Differential
checks compare original/optimized packets, bar-local scratch values and complete
checkpoints, plus randomized short/missing histories and VP bins.

An unprofiled local 2,000-candle comparison improved from 5.451 s (367 bars/s) to
3.881 s (515 bars/s), with identical packets/checkpoint/formula fingerprints.
The standalone benchmark with 500 warm-up + 1,000 measured candles gave 368 vs
506 bars/s, a 1.37x calculation speedup. These are synthetic CPU results, not Mac
production download, database or wall-clock catch-up rates.

Normal scheduled maintenance now accepts up to 1,000 rows rather than stopping at
200, within the same one-second calculation budget. Non-owner service retains its
quarter-budget allowance; network, decision processing, audit and live event
budgets remain bounded. Compatibility catch_up/event calls still use their
existing smaller batches. Atomic feature+checkpoint commits are retained.

Normal feature logs report overall batch rows/s, calculation-phase ms/bar and
commit time. The calculation phase includes any required daily-source reads;
the total includes metadata/reads/checkpoint/SQL overhead. Scheduled waits and
other runner phases are outside the batch rate. Use successive checkpoint times
and real elapsed wall time to assess sustained production catch-up.

Run on the target machine without writing production data:

```sh
python3 benchmark_features.py --bars 1000 --warmup 500 --compare
```
