# Offline confirmed-pair pivot trial

This experiment tests the three proposed rules on the Mac's exported ENAUSDT 15m
candles. It changes no production engine, UI, runner, strategy or database.
Open `comparison.html` directly in a browser; no server or external requests are
needed. `comparison.png` is the static overview. The interactive view can switch
between pivot-origin labels and the candles where confirmation became known.

## Exact rules tested

1. Track the highest high after the previous confirmed low's origin, or the lowest
   low after the previous confirmed high's origin. A strictly new extreme replaces
   the candidate and resets close confluence. Equal extremes retain the first origin.
2. Freeze `abs(last confirmed high - last confirmed low)` during candidate
   development. Require a reversal of at least 25% of that range from the candidate.
   Update the confirmed pair only on confirmation. Decimal arithmetic implements
   inclusive threshold equality, rather than binary floating-point near misses.
3. Confirmation needs two consecutive strictly lower closes for a high or strictly
   higher closes for a low. These compare close-to-previous-close, not candle color.
   Both occur after the candidate origin. Equal/interrupted closes reset the count;
   the distance condition must hold on the candle that confirms. No same-candle
   double confirmation or confirmation on the candidate's own candle is allowed.

The next opposite extreme includes candles already observed after the pivot
origin, even if they precede recognition of that pivot. The origin candle itself
is excluded from the opposite-extreme search because its high/low ordering is
unknown from OHLC. Close confluence resets when that opposite candidate activates.
A late-activated candidate must not discard more extreme already-observed prices.

## Seed and limits

The first exported closed candle provides the existing known confirmed high/low
and active candidate. The close counter starts at zero. This avoids inventing a
cold-start rule but makes the result specific to that boundary. The full comparison
covers the next 5,999 candles; there are 6,000 candles including the seed.

The experiment is a standalone pivot state machine, not a full replay of the
production feature engine. In particular it does not run structure/BOS resets,
classifications, dependent features, an execution strategy or a P&L simulation.
The stored baseline is the exported production result, not a newly recomputed
baseline. Historical recursive production integration still needs separate work
if this specification is selected. Counts are not proof of predictive accuracy.
No 1h/4h dataset has been tested here.

## Results

| Rule | Confirmations | High / low | Confirmations on adjacent candles | Median origin-to-confirmation candle lag |
|---|---:|---:|---:|---:|
| Current stored | 1,768 | 884 / 884 | 607 | 1 bar |
| Confirmed-pair reference without close confluence | 1,811 | 906 / 905 | 531 | 1 bar |
| Confirmed-pair reference and two reverse closes | 528 | 264 / 264 | 0 | 3 bars |

The full proposal reduces total confirmations by about 70% in this sample, while
recognition occurs later. Adding the close condition necessarily prevents
adjacent-candle confirmations in this state machine.

The long decline in the screenshots changes too: from the 0.1155 high's origin
to the 0.0904 low's origin, the stored baseline has only those two pivot labels.
The full proposal has eight: high 0.1155, low 0.0989, high 0.1031, low 0.0968,
high 0.0994, low 0.0958, high 0.0972, low 0.0904. Thus it removes much earlier
clutter overall but does not preserve that entire decline as a single swing.
This is a consequence of changing the reference and subsequent recursive anchors.

## Reproduce

From the repository root:

```bash
python3 Section_12_Research/experiments/pivot_confirmation/trial.py \
 Section_12_Research/reports/pivot_debug/ENAUSDT-15m-20261126/stored-pivots.json.gz \
 --output /tmp/pivot-trial.json
python3 -m unittest Section_13_Development.tests.test_pivot_confirmation_trial
python3 -m Section_13_Development.tests.browser_pivot_trial
```

`build_view.py` recreates the self-contained HTML with `--output PATH`; optional
`--png PATH` requires matplotlib. Unit tests cover frozen reference ranges,
candidate replacement, interrupted/equal closes, symmetric high/low rules,
threshold equality, gaps, preservation of extremes before delayed activation,
prefix stability (no future-candle changes), and all proposed events in this export.
