# First causal overlap prototype: rejected

The fixed first hypothesis **does not demonstrate a tradable edge**. Preserve
this failed version as a comparison; do not promote it to live BUY/SELL rules.
It Section_13_Development/tests one possible timing/exit interpretation, not every possible use of
the recurring measurements.

Source: the same 80,692-candle frozen BTCUSDT 1h export through 5 November 2026,
21:00 PKT. Every eligible hourly close is evaluated, including candles unrelated
to eventual successful pivots. The analyzer excludes 14 shortened/invalid price
candles, detects 31 price discontinuities and censors affected positions.

The [configuration](spot_overlap_hypothesis_v1.json) separates prior EMA50
up/down/mixed context, requires current activity and price reclaim, and allows
pressure events recognized on different recent closes. Mixed context is not
claimed to be a proven range. SELL requires price/control loss, EMA50 loss, or
exhaustion with price weakness. Its source generator is
[prototype_config.py](prototype_config.py). No retrospective pivot/outcome or
Section 5 context field is an input.

Both strategies start flat, alternate one BTC position with cash, evaluate at
closed candles and fill at the next valid contiguous open. The modeled fee is
10 bps per side and slippage 2 bps per side. These are assumptions, not the
user's verified account fees. The DI baseline is replayed on the identical input,
dates and costs. No parameter search or second attempt followed these results.

| Metric | Overlap prototype | Independent DI-turn baseline |
|---|---:|---:|
| Entries | 3,387 | 2,676 |
| Completed trades | 3,382 | 2,657 |
| Censored trades | 5 | 18 |
| Open trades at cutoff | 0 | 1 |
| Positive net trades | 947 | 1,436 |
| Net win rate | 28.00% | 54.05% |
| Mean net return per completed trade | -0.258% | -0.200% |
| Profit factor from summed trade returns | 0.582 | 0.740 |

The prototype's mean raw open-to-open movement before modeled fees/slippage is
also slightly negative (about -0.018%). Costs are not the sole problem.
The baseline's higher win rate also fails to establish positive expectancy.

| BUY branch | Completed trades | Positive net trades | Mean net return |
|---|---:|---:|---:|
| Up-context pullback proxy | 1,733 | 476 | -0.220% |
| Down-context reversal proxy | 1,317 | 382 | -0.310% |
| Mixed-context recovery proxy | 332 | 89 | -0.249% |

Every inspected calendar-year slice has a negative mean net return. These
are inspected descriptive slices, not independent validation. Aggregate
extreme-to-extreme pivot success does not translate automatically to entry and
exit success at available fills.

The [full offline report](prototype_replay/strategy_analysis.html) includes all
signals, trades, branch diagnostics, yearly results and baseline revisions.
Its [compressed data](prototype_replay/strategy_analysis.json.gz) retains exact
signal inputs, missingness, source digest and configuration. Closed-trade
compounding in that report assumes the whole balance is reinvested each time;
it excludes open/censored positions and is not a complete account equity curve.

This prototype has **no protective stops, fixed entry-relative targets or time
exits**. Those remain explicit implementation gates in
[INDICATOR_SPEC.md](INDICATOR_SPEC.md). The current analyzer cannot express
entry-price-dependent stops/targets using only its scalar feature predicates.
The result rejects this particular simple overlap/exit combination. It does
not validate a future strategy, justify removing costs, or justify tuning
thresholds until the historical report turns positive.

Reproduce from the repository root:

```sh
python3 Section_12_Research/reports/BTC_1h_spot_overlap/prototype_config.py
python3 Section_12_Research/cli/analyze_btc_hour_strategy.py \
  --input Section_12_Research/reports/BTC_1h_sequences/source_v1.json.gz \
  --config Section_12_Research/reports/BTC_1h_spot_overlap/spot_overlap_hypothesis_v1.json \
  --baseline-config Section_12_Research/reports/BTC_1h_spot_overlap/di_baseline_same_costs.json \
  --output-dir Section_12_Research/reports/BTC_1h_spot_overlap/prototype_replay
```

Eighteen existing strategy-analyzer tests passed. Replay checks confirm unique,
alternating signals and no unavailable feature columns. The exact-pair study
and Section 5 readiness checks remain separate from this trade replay.
