# Read-only scalping research

The current `evaluate_strategy.py` studies independent DI signal events. It uses
next-bar-open entry and exits at fixed future candle closes. It does not simulate
positions, stops/targets, capital, leverage, drawdown, funding or executable fills.
The underlying candles are spot, not perpetual execution prices. Neither high
win rate nor positive historical event means establish a tradable strategy.

The initial user-supplied 5m report on BTC/ETH/ENA had roughly zero gross mean
returns over 5/15/30 minutes. At 30 minutes, average gross returns were about
-0.04 bps BTC, -0.43 bps ETH and +1.00 bp ENA, versus the assumed 12-bps round-trip
cost. These are the supplied aggregate results, not measurements reproduced
against production data in this workspace. There is no demonstrated standalone
DI edge under these entries/exits. This does not establish that all conditional
setups or structural exits fail.

Before choosing a setup, inspect recent BUY/SELL results separately and compare
chronological periods. Do not select a lucky symbol, horizon or side after looking
at many alternatives and call it an untouched holdout. Specify the candidate and
its parameters before a final future paper-trading or held-out evaluation.

Example (date-only bounds are UTC midnight):

```sh
python3 evaluate_strategy.py \
  --symbols BTCUSDT ETHUSDT ENAUSDT --intervals 5m --horizons 1 3 6 \
  --cost-bps 12 --since 2026-08-01 --until 2026-10-28 \
  --split-at 2026-10-01 --summary --output scalp_recent_12bps.json
```

`--summary` prints a small period/side/horizon table. The output file retains full
JSON including sample counts, actual signal/outcome coverage and gross/net means.
Theoretical break-even cost is mean gross bps, using the same fixed-cost model;
a negative number means even zero costs would not make the mean positive.
Actual costs depend on venue, order type, size, spread and depth. Gross means in
a fixed-cost study can be recovered by adding the assumed cost to net means.
Gross win rates cannot be inferred that way; this evaluator reports them directly.

A signal belongs to a window by when its closed candle becomes available. Earlier
rows seed the original DI gate and alternation without adding window observations.
The reader still streams the committed prefix, so a recent window does not skip
historical gate warmup. Entries occur on the next candle; unavailable tails and
gaps cannot generate fabricated exits. Outcomes cannot cross the requested end;
unfinished earlier-period events are purged at the split. This is a descriptive
chronological comparison, not an optimizer or proof of generalization. Horizons
within a signal and overlapping signals are correlated observations.

Next research stage: compare a predefined trend-aligned pullback setup with DI
alone, then compare adding fresh observed-liquidity confirmation on the **same
recorded period**. This requires an execution-aware, bounded-position simulator
and aligned market data. Candle-derived inferred levels and observed perpetual
orders remain separate. Do not backfill missing historical order flow with current
observations, treat unavailable data as zero, or silently mix spot fills with
perpetual fees/leverage. Live decision, confidence, opportunity and recorder
rules are unchanged by this diagnostic.
