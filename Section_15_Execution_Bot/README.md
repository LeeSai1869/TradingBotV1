# Isolated Spot paper bot

This phase tests the complete strategy-to-fill/accounting path with **simulated
fills**, public Binance Spot bid/ask quotes, configurable stop-loss/take-profit,
and an independent SQLite ledger. There is no authenticated Binance client,
order endpoint, API-key setting, TradingView webhook, or real-money mode.

The existing chart and market-data runner do not import or start this worker.
One worker can manage multiple named coin/timeframe allocations. It reads only
confirmed events from the enabled, selected strategy instance for each pair.
Comparison instances cannot place paper orders. No signals or indicators are
recomputed by the bot. Strategy source/version fingerprints must match.

Each allocation has a separate USDT paper balance and one long Spot position.
SELL closes its position; it never shorts or sells another allocation's holdings.
Initial capital and maximum capital per entry are configured separately. Net
realized proceeds, after fees, automatically compound; cash above the cap stays
in reserve. These allocations are virtual wallets, not a claim against an actual
Binance account balance. A future live adapter must enforce shared wallet limits.

## Setup

First enable/select a strategy through Settings → Features → Strategies, or use
Core's strategy-management API. This does not activate an inactive market pair.
Get its `instance_id` from the strategy catalog. Then, from the repository root:

```bash
python3 -m Section_15_Execution_Bot create --name ena-5m \
  --symbol ENAUSDT --interval 5m --instance-id YOUR_SELECTED_INSTANCE_ID \
  --capital 100 --capital-cap 200 --stop-loss-pct 2 --take-profit-pct 4
python3 -m Section_15_Execution_Bot enable ena-5m
python3 -m Section_15_Execution_Bot run
```

The numbers above are examples for paper testing, not recommended trading
parameters. Supply your chosen capital, cap and exit percentages. Default modeled
fee is 10 bps and slippage is 5 bps on each side; both are configurable at creation.
`--db PATH` before the subcommand selects another private ledger; default is
`~/.tradingindicator/paper-bot.sqlite3`. `status` shows configuration, cash,
position, realized P&L and last successful quote receipt. `run --once` performs one
bounded turn. `pause NAME` stops new entries, **not protection of an open position**.
Keep the worker running to monitor exits. Ctrl+C stops it; positions/state survive
restart, but no stop-loss or take-profit runs while the process is offline.

Stop-loss/take-profit use the executable modeled bid including sell slippage,
relative to the entry fill price (fees are recorded separately). Public quotes are
locally receipt-timestamped because Binance bookTicker has no exchange timestamp;
slow requests, invalid spread, wrong-symbol, stale/future quotes produce no fill.
A market gap can cross the stop; there is no guaranteed exit price.

BUY/SELL events, fills and cursors commit atomically. Duplicate polling/restarts
cannot repeat a consumed event. Events before activation or older than three
minutes are ignored; enabling again does not replay paused signals. Selected
strategy removal/switching or inactive pair blocks new entries. Existing positions
retain their configured protective exits even if the signal feed is unavailable.
A data-generation change halts strategy orders and requires a newly reviewed
allocation; protective exits remain active. Paused allocations may still consume
fresh strategy SELL exits. Closing a position via a risk exit cannot immediately
reenter in the same turn.

SQLite serializes concurrent ledger writers, but run one supervised worker per
ledger to avoid duplicate quote polling. For 24/7 availability, supervise it on an
always-on host after paper validation. A sleeping/offline Mac cannot provide
24/7 protection. Nothing in this change installs/enables a login service.

## Before real execution

A separate implementation/review must add Binance symbol filters and quantity
rounding, authenticated testnet orders, idempotent client order IDs, partial fills,
exchange reconciliation, shared wallet reservations, exchange-native protection,
and credential storage. Paper fractions do not enforce LOT_SIZE/MIN_NOTIONAL and
paper fills do not model order-book depth. No real-money trading is enabled here.

## Offline proof before connecting a paper feed

`python3 -m Section_15_Execution_Bot demo` runs BUY → take-profit → BUY → stop-loss
using deterministic quotes in a disposable temporary ledger. It makes no network
requests, uses no app data and leaves your normal ledger untouched. To review a
running allocation's fills: `python3 -m Section_15_Execution_Bot history ena-5m`.
Errors appear in worker output and account status; a failed quote never fabricates
a fill, and the last successful quote timestamp remains visible for liveness.
