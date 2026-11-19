# Runner focus and Regime throughput review

13 November 2026, Pakistan time.

## Findings

The observed process was still emitting `stage=downloads/features` and repeated
`maintenance_classifications=0`, while the source tree already contained the
newer pair-ready scheduler. This supports a loaded-code/deployment mismatch.
Old feature records alone do not establish that their current formula generation
and replay checkpoints are complete. Ready timeframes should nevertheless keep
advancing independently of another timeframe's repair backlog.

The bulk source/feature owner previously ended when those checkpoints finished.
Full analytical history used a separate round-robin queue across all ready
coins, so no single coin owned the whole historical hierarchy. History also
received only the live analytical row budget's remainder. A saturated live
turn could therefore allocate zero rows to historical work.

A dependent's cached complete-prefix flag could survive later progress in its
children. That is now invalidated through the declared dependency registry.

Live verification identified a separate blocker in the chart backend: its
closed-alert evaluator held the market-data writer lock while reading candles
and preparing notification context. The UI process repeatedly occupied that
coordination lock while analytical turns timed out. Alert preparation now uses
the reader guard, releases it, then takes a short writer lock and revalidates
the policy epoch, active scope and rule revision before committing notifications.
Policy changes and edits cannot publish the stale prepared result.

The newly activated pipeline also exposed a decision paging error: the per-turn
100,000-row allowance exceeded the public reader's 1,000-row page maximum. Each
decision batch now respects the page maximum independently of the turn budget.

## Measurement

A read-only replay of 2,048 mature BTC 1h input bundles took 0.084 seconds,
about 0.041 ms per Regime classification or 24,400 classifications/second.
All replayed outputs had VALID input coverage. This measures the pure classifier,
excluding source setup, locks, writes and scheduler waiting.

A separate cProfile run over 200 rows used a temporary intelligence database,
leaving production history unchanged. Under profiler overhead it spent 1.171
seconds overall: 0.024 seconds in classification, 0.015 in projection and
0.030 in the commit. Cold feature-catalog initialization consumed about 0.744
seconds and waiting for the shared policy lock about 0.312 seconds. Catalog
initialization is a one-time process cost; this sample is not steady-state
production throughput.

Regime reuses the stored indicators. The observed zero-progress periods cannot
be explained by expensive Regime mathematics.

## Changes delivered

- Persist the current bulk coin in the existing pipeline state and retain it
  through downloads, current-generation features, all compatible historical
  engine cursors and decision-rule checkpoints. Resume after restart; release
  a paused/removed owner or a completed owner.
- Restrict bulk downloads, feature work and analytical history to that coin.
  Ready frames can advance before every frame of the owner finishes repair.
- Preserve bounded recent download/feature/classification service across active
  coins. Historical decision tails outside the owner wait; small recent tails
  still have a separate slice before the owner's decision turn.
- Give live and historical analytics independent explicit row/time allowances.
  Use the classifier's existing 200-row transaction maximum.
- Clear dependent completion flags when an upstream engine advances. Keep the
  registry's Structure -> Trend, Trend/Structure/Participation -> Phase, and
  nine-base-engines -> Bias dependencies.
- Log rows/s, pure calculation time per row, projection time and commit time.
- Keep alert preparation outside the market writer lock, with policy/revision
  revalidation before saving; enforce the decision reader's page limit.

Classifier formulas, engine/config versions, gateway source and immutable run
identities are unchanged. Compatible histories continue from their old cursors.
No feature/ADCN fields, stored generations or canonical candles were deleted.
The active symbol/timeframe universe is unchanged.

## Verification and activation

123 scheduler/history Section_13_Development/tests passed, covering resume/lineage, hierarchy, focus retention,
separate lane budgets, recent-service fairness, source generations, decision
alternation and resource lifetimes. Runner dependency preflight passed with its
existing `.venv-build` interpreter; `git diff --check` passed.
An additional 25 targeted alert/decision checks passed, including writer
availability during preparation, discarding a notification if its scope pauses,
stale rule edits, deduplication and the decision reader's page cap.

With the user's explicit approval, only the existing `com.tradingindicator.chart`
and `com.tradingindicator.liverunner` services were restarted using launchctl.
Their launch-agent configuration, alert rules and data were preserved. No
service was reinstalled or disabled.

Post-restart logs show persisted BTCUSDT focus, the per-pair scheduler and
nonzero live/historical analytical maintenance. BTC 1h live Regime advanced
18 closed candles at roughly 943 rows/s for that batch, with about 0.044 ms of
classification per row. Historical 200-row batches report hundreds of rows/s;
their commits, not classification mathematics, take most of the measured batch
time. Full historical coverage remains unfinished. No wall-clock completion
promise follows from the pure classifier benchmark.

[The verification snapshot](../Section_12_Research/reports/runner_focus_fix_20261113/verification.json)
records persisted BTC focus, advancing 1h/4h cursors, reuse of existing compatible
run IDs and zero new runner-error bytes during the final observation window.
The restarted chart backend also returned HTTP 200 from its session health check.

## Strategy and storage

[Section_12_Research/docs/STRATEGY_INPUT_REVIEW.md](../Section_12_Research/docs/STRATEGY_INPUT_REVIEW.md) separates candidate entry,
context and risk measurements from archived scoring/compatibility fields.
The intended sequence remains strategy definition and validation first, then
dependency/consumer audit and memory pruning. Physical column presence is not
evidence of strategy usefulness; an unprofitable first prototype is also not
enough evidence to delete every field it used.
