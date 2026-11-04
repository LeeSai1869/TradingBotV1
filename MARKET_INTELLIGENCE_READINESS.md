# Market intelligence: implementation and validation status

All ten Section 5 engines and the separate multi-timeframe aggregator are connected
to existing bounded analytical processing. They remain analytical outputs; no new
trading rules, chart overlays, notification behavior or recorder scheduling are
introduced by this completion work. Existing Section 4 measurements are reused.

## Implemented versus unfinished

| Area | Status |
|---|---|
| Regime, Trend, Structure, Momentum, Volatility, Participation, Phase | Independent versioned engines and stored history |
| Liquidity | Structural interpretation plus explicitly scoped recorder observations; source gaps stay unknown |
| Sentiment | Derivatives context; optional scored news/social ingestion prepared, not connected |
| Bias | Versioned synthesis; no automatic entry/exit, no invented sentiment directional edge |
| Multi-timeframe aggregation | Separate causal/as-of aggregation and provenance |
| Operational readiness | Read-only report across configured active symbol/timeframe scopes |
| Directional outcome research | Read-only forward-return event study; not strategy/portfolio validation |
| External positioning | Funding normalization/account-ratio acquisition still missing |
| Predictive validity | Not established by implementation or synthetic tests |

## Check your real data

The development workspace has no production candle/feature databases. Run on the
laptop containing your actual data after pulling and restarting the runner:

```bash
python3 intelligence_status.py --summary --output intelligence_readiness.json
```

With no symbol/timeframe filters, this uses the active registry. It reports all ten
engines per pair, indexed current producer/run identity, latest classifications,
coverage, confidence, source scope, publication time, S4 replay blockers and stale
or backlogged results. It reads existing databases; it never creates engine or raw
market stores or starts calculations. Default pair cap 1000 is explicit; truncation
is reported. `PARTIAL` may be expected for optional external sources; `VALID` alone
does not establish predictive quality.

## Evaluate saved directional states

```bash
python3 evaluate_intelligence.py --engine BIAS \
  --symbols BTCUSDT ETHUSDT ENAUSDT --intervals 5m \
  --horizons 1 3 6 --cost-bps 12 \
  --since 2026-10-01 --until 2026-11-04 --split-at 2026-11-01 \
  --summary --output bias_actual_publication.json
```

5m is an example, not a restriction. Omit `--intervals` to use active timeframes.
This evaluates existing indexed normal-runner output only; it never silently
reprocesses engines, selects an arbitrary old cohort, or adjusts thresholds. Default
events are confirmed directional transitions. `--every-close` studies every eligible
directional close instead, with correlated repeated observations explicitly disclosed.
`--min-confidence` and `--min-coverage` take fractions [0,1], not percentages.

Default ACTUAL publication uses the saved result's real `available_at`. A result
published during a candle enters at the next eligible open, never the old open of
the candle already forming. Stale-at-publication reconstructions are excluded. If
history was computed long after the fact, ACTUAL may legitimately have no outcomes.

`--reconstructed-close` is a separate hypothetical study using the engine's causal
closed-candle `as_of`. It assumes results could have been computed then; it does not
prove they were published then. Source projections still contain only information
available at that original boundary. Keep these reports separate.

Returns are signed spot-price changes to fixed-horizon closed candles, less an
assumed fixed round-trip bps cost. Missing candles, unconfirmed outputs, insufficient
future bars and cross-split/end outcomes are excluded with reasons. Defaults scan at
most 100000 stored rows and 20000 events per pair; truncation is visible. Dates apply
to publication/event availability; earlier rows seed transition state. Outcomes
crossing the earlier/later boundary are purged.

This is descriptive research, not portfolio P&L. It has no position sizing, competing
trades, stop/target fills, funding, observed execution slippage or drawdown simulation.
Overlapping horizons/events are correlated. A chronological split does not become an
untouched holdout once inspected/tuned. Freeze hypotheses first, then compare future
holdout performance and costs before changing decisions. No profitability claim is
made by this tool.

## Optional sources

See [Sentiment 1.1](Section_5_Market_Regime/SENTIMENT_V1_1.md) for configuration,
canonical observations, disabled example and explicit remaining source gaps. There
is no automatic subscription, scraper, news model or provider selection.
