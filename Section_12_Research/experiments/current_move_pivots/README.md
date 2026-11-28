# Offline current-move pivot trial

**Status: research only. Do not change the production writer or schedule a replay from this branch.**

## Rule under test

For a candidate high, use `candidate high − last confirmed low` as the current move.
Confirm after a closed candle has reversed at least 25% of that distance and two
consecutive closes are strictly lower than their preceding closes. Mirror this
for a candidate low. A new extreme updates the distance and resets the close count.
Equal/interrupted closes reset the count. Candle color is irrelevant. The second
close and the distance test must coincide; a prior wick touch is insufficient.

The previous confirmed opposite pivot remains the anchor until the candidate is
confirmed. The next candidate retains the opposite extreme observed after that
pivot origin, excluding its own candle because OHLC cannot establish intrabar order.
Confluence restarts on activation; at most one pivot is confirmed per candle.

This changes only the reference-distance definition compared with the current
confirmed-pair rule. No volatility floor, minimum leg size or additional condition
was added. Both controls use the same seed and closed input candles.

## Archived-data results

| Archive | Candles | Existing pair + 2 closes | Current move only | Current move + 2 closes |
|---|---:|---:|---:|---:|
| ENAUSDT_15m | 6,000 | 528 | 1,780 | 568 |
| BTCUSDT_1h | 12,000 | 1,204 | 3,476 | 1,280 |

- Compared with current-move distance alone, the close filter removed about 68%
  of ENA confirmations and 63% of BTC confirmations. Adjacent-candle confirmations
  fell from 616 and 1,132 respectively to zero.
- Compared with the existing confirmed-pair + two-close rule, pivot counts rose
  approximately 7.6% on ENA and 6.3% on BTC. Median recognition lag remained three bars
  on both archives; this does not promise earlier recognition for every pivot.
- In descriptive 64-candle windows with net close progress no more than 20% of
  total close-to-close travel, median counts were 7 vs 6 on ENA and 7 vs 7 on BTC
  (current-move + closes vs existing rule). These window definitions are analysis
  labels, not additional pivot conditions.
- Two-close confirmation produced no ENA legs below 0.25% of the prior pivot price.
  BTC had three such legs, with the smallest about 0.166%. These are descriptive
  measurements, not a newly imposed threshold or a performance claim.

## Your numeric example

The separate constructed example assumes the low 0.1302 is already confirmed.
A candidate high of 0.4802 gives a move of 0.3500 and a required reversal of 0.0875.
The high-confirmation close level is 0.3927. Closes of 0.43 and 0.38 meet both
conditions. The confirmed-pair baseline using 0.5818/0.1302 would not confirm there.
This is a numerical test, **not recovered historical candles from the screenshot**.

## Limits: shrinking swings and actual crash data

Two consecutive closes do not impose a minimum price distance. A constructed
sequence with halving swings still produces 30 confirmations with the proposed
rule, all with two reverse closes, and eventually extremely small legs. The existing
confirmed-pair rule also shrinks on this stress case. The close filter greatly
reduces observed label density but does not mathematically eliminate this behavior.
No additional condition is recommended or implemented in this trial.

The ENA archive contains 6,000 15m candles from 25 September to 26 November 2026
(Pakistan time). BTC uses the last 12,000 1h candles of its archive, from 23 June 2025
to 5 November 2026. These have different market histories and timeframes.
The exact ENA 4h October 2025 crash is absent from the available export. A public
archive download was blocked by the environment network policy. That specific
sequence still needs an actual 4h candle export before any production decision.

Both data sets start from archived information known at the first replay boundary;
they are not a comparison of full cold-start engine initialization. BTC uses the last
two archived opposite pivot events known at the boundary and the observed subsequent
candidate extreme. Initial close streaks start at zero. Seeds, dates and input SHA-256
hashes are recorded in `results/summary.json`. Historical pivots are not trading returns.

## Review without installing anything

Open `results/ENAUSDT-15m-comparison.html` directly in a browser. Switch between
origin and confirmation placement, move through the candles, and inspect the
candidate price, distance threshold and reverse-close count. The top chart replays
the current production rule; the lower chart switches between the proposed rule
and its no-close-filter control. No app server or external request is required.

`results/constructed-price-example.html` illustrates only the supplied numbers.
The event JSON files retain origins, confirmation times, known times, anchor prices
and thresholds for auditing. The files are independent research artifacts.

Reproduce from the repository root:

```bash
PYTHONPATH=. python3 -m Section_12_Research.experiments.current_move_pivots.evaluate
PYTHONPATH=Section_13_Development/tests:. python3 -m unittest test_current_move_pivot_trial test_pivot_confirmation_trial -q
PYTHONPATH=. python3 Section_13_Development/tests/browser_current_move_trial.py
```

No application formula, feature registry, checkpoint, active timeframe, runner
configuration, UI or database is changed. Source archives are read only.
