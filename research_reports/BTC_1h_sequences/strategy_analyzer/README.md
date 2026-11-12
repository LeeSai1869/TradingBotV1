# First complete alternating strategy replay

For the visual strategy editor and configurable reports, run
`python3 analyze_btc_hour_strategy.py --serve` from the repository root. Strategy
branches, AND/OR groups, input exports, dates, costs and baseline selection are
configured inside that browser workspace. The HTML here remains an offline
report with its own trade/indicator filters, selectable columns and CSV export.

These are demonstration rules for validating the analyzer, not a selected or
profitable strategy. The four-branch revision and independent DI baseline were
replayed over every candle in `../source_v1.json.gz`, using the configs in
`../strategy_configs/`. Neither replay requires native-pivot membership. Both use
4 bps fees and 2 bps slippage per side, next-open fills, and start flat waiting for
BUY. No production logic or live memory was changed.

| Result | DI baseline | Four-branch example |
|---|---:|---:|
| Accepted BUYs / entries | 2,676 | 1,335 |
| Accepted SELLs | 2,675 | 1,334 |
| Completed trades | 2,657 | 1,318 |
| Profitable completed trades | 1,659 | 848 |
| Losing completed trades | 998 | 470 |
| Win rate among completed trades | 62.44% | 64.34% |
| Mean net return per completed trade | −0.0803% | −0.0838% |
| Closed-trade compounded return | −95.41% | −86.01% |
| Open / censored trades | 1 / 18 | 1 / 16 |

The higher example win rate **does not** establish a successful strategy: its
mean net trade return is negative and its closed-trade balance loses value. The
closed-trade compounded return excludes censored/open positions and is not a full
account return. Drawdown reported in the JSON is at completed-trade endpoints,
not intratrade. Neither version has protective stops or time exits.

Revision diagnosis matches accepted BUY times after replaying the complete
chronology:

- Previous successes preserved: **470**; lost: **1,187**; unresolved: **2**.
- Previous failures corrected to profitable exits at the same BUY: **53**.
- Previous failures whose BUY disappears: **708**, separately labeled removed,
  not counted as corrected; failures persisted: **236**; unresolved: **1**.
- New BUY entries: **529**.

This example therefore does not meet a goal of preserving prior successful cases.
The analyzer now makes that regression explicit rather than reporting only the
failed cases that improved. Inspect the failure/lost-success cohorts before
proposing the next feature branch, then replay the whole sequence again. No
threshold was tuned after observing these results.

Input integrity: **80,692** candles scanned; **80,678** valid full-hour price
candles evaluated; **14** shortened historical candles excluded; **31** continuity
gaps detected. These counts can overlap. Affected trades are censored, while the
BUY/SELL sequence remains strictly alternating. Engine context is sparse in this
frozen export; explicit OR alternatives can use exported price/features, and
remaining unknown results are reported rather than filled with neutral values.

The HTML contains complete accepted signals, trade inspection with signal inputs,
branch/missing-data diagnostics, chronological results for 2017–2026 and revision
cohort selectors. It works offline without unpkg.com. `strategy_analysis.json.gz`
contains the complete machine-readable report, configuration and input fingerprint.

Reproduce from the repository root:

```sh
python3 analyze_btc_hour_strategy.py \
  --input research_reports/BTC_1h_sequences/source_v1.json.gz \
  --config research_reports/BTC_1h_sequences/strategy_configs/multi_branch_v1.json \
  --baseline-config research_reports/BTC_1h_sequences/strategy_configs/di_baseline_v1.json
```

See `BTC_1H_STRATEGY_ANALYZER.md` for expression syntax, current-memory export,
evaluation windows and comparison with a saved baseline. These inspected yearly
results are descriptive research, not untouched holdout validation.
