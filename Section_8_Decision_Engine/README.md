# Closed-candle DI turning-point decisions

The single active strategy is [rules/di_turning_point.py](rules/di_turning_point.py).
It applies to every enabled timeframe. Sections 6 and 7 and the old Section 8
scoring engine have been removed. Sections 9 and 10 are retained; their existing
score packet import now points at `contracts.py`. They are not newly activated,
and this strategy does not invent confidence scores or execute exchange orders.

The rule is a direct translation of the supplied Pine function. Write a, b, c for
three successive closed candles (oldest first), and spread = abs(+DI − −DI).

BUY outer gate:
- a.−DI < b.−DI > c.−DI;
- a.spread < b.spread > c.spread;
- c.close > b.close;
- c.ADX > b.ADX.

Then either:
- −DI < +DI on a and b, and −DI > +DI on c; or
- b.spread > b.+DI, and −DI > +DI on all three candles.

SELL mirrors these conditions using a peak in +DI, a falling close, rising ADX,
and either a transition from +DI < −DI to +DI > −DI, or +DI dominance throughout
with b.spread > b.−DI. Every comparison is strict. BUY and SELL are evaluated as
independent `if` statements in Pine order. No regime/config filter is added because
the supplied function does not use those arguments. Unavailable required values
produce WARMUP, not a signal. The older candle's ADX/close are not required.

The existing runner invokes Section 8 after Section 4. Inputs come from the same
stored raw bars and committed formula-v3 features used by the chart. Feature
checkpoint caps, gaps, close times, atomic decision/checkpoint commits, and policy
epoch checks prevent use of provisional or skipped data. Signals appear through
the combined chart stream as BUY/SELL markers. Rule version 2 invalidates the old
rule's transient/checkpoint state and seeds the latest calculated three-bar window.
Older stored decisions remain historical records, not re-evaluated v2 results.

## Historical evaluation

Run from the project folder:

```bash
python3 evaluate_strategy.py --symbols ETHUSDT --intervals 5m 15m 1h 4h --output strategy_report.json
```

Omit symbol/timeframe filters to evaluate all available committed pairs. Only
formula-v3 data through the feature replay checkpoint is included. Re-run after
replay completes for coverage of the latest regimes. The command opens databases
read-only and never changes runner state or stored decisions.

This is an independent signal event study: signal on the closed bar, entry at
the **next candle's open**, and returns at 1, 3, 6 and 12 candles from entry.
SELL returns use the short direction. Overlapping signals are separate events,
not a portfolio. Gaps discard unfinished observations; incomplete tails do not
create returns. Default results are gross: pass `--cost-bps 10`, for example,
for a total 0.10% round-trip fee/slippage assumption. No exits, stops, sizing,
funding, or fill model were supplied, so this cannot establish strategy P&L.

Validation in this cloud checkout: 10,000 generated windows matched a separate
Pine-condition translation; both BUY and SELL branches and closed-memory commits
were tested. The available cloud candle/feature tables are empty, so a historical
market performance result cannot be reported here. Use the command above on the
Mac containing the downloaded history.

## Momentum Indicator presentation

Settings → Features → Momentum Indicator exposes independent BUY/SELL visibility,
color, size, shape and label controls. The combined bar reader includes a
read-only `momentum` projection from this same rule, using two extra predecessor
candles at page boundaries. It does not depend on historical ADCN backfill or
create a second strategy implementation in JavaScript. Existing decision rows
remain unchanged. Only closed formula-v3 feature rows participate; gaps reset
lookback, and provisional candles cannot create a marker. A historical report
never wrote decisions, which previously left most counted signals invisible.
Where current features are still replaying, current markers must wait for them.

BUY/SELL sounds can each be None, Chime, Bell or Alarm, with volume and test
buttons. Choosing a sound and applying settings unlocks browser audio; after
reopening, use Enable signal sounds once if the browser blocks audio. Delivery
only watches the open symbol/timeframe, deduplicates each candle/direction, and
ignores candles closed before entering that chart. Historical loads, settings
redraws and switching charts do not replay old sounds. Hiding the indicator or a
direction mutes its sound. Defaults are silent until configured. This uses the
existing alert audio system and does not create account-wide alert rules.
