# Isolated Spot paper bot

This phase tests the complete strategy-to-fill/accounting path with **simulated
fills**, public Binance Spot bid/ask quotes, configurable stop-loss/take-profit,
and an independent SQLite ledger. There is no authenticated Binance client,
order endpoint, API-key setting, TradingView webhook, or real-money mode.

The existing chart and market-data runner do not import or start this worker.
One worker can manage multiple named coin/timeframe allocations. It reads only
confirmed BUY/SELL decisions already committed by the existing live Section 8
strategy for each pair. The default `--strategy current` needs no new strategy
selection screen, registry or per-strategy tables. The rule is not duplicated or
recalculated by the bot. Its installed source fingerprint is pinned at allocation
creation; later source changes block new strategy orders until reviewed.

If the optional strategy lifecycle extension is installed and manages that pair,
current mode reads its selected instance instead. Inactive/comparison instances
cannot execute. `--instance-id ID` remains available for explicit binding. A
selection/strategy-generation change halts strategy orders for an existing
allocation; its configured protective exits remain active.

Each allocation has a separate USDT paper balance and one long Spot position.
SELL closes its position; it never shorts or sells another allocation's holdings.
Initial capital and maximum capital per entry are configured separately. Net
realized proceeds, after fees, automatically compound; cash above the cap stays
in reserve. These allocations are virtual wallets, not a claim against an actual
Binance account balance. A future live adapter must enforce shared wallet limits.

## Setup

Use an already active coin/timeframe with a current committed decision checkpoint.
No chart settings or runner changes are required. From the repository root:

```bash
python3 -m Section_15_Execution_Bot create --name ena-5m \
  --symbol ENAUSDT --interval 5m --strategy current \
  --capital 100 --capital-cap 200 --stop-loss-pct 2 --take-profit-pct 4
python3 -m Section_15_Execution_Bot enable ena-5m
python3 -m Section_15_Execution_Bot run
```

Coin and timeframe remain configurable; ENAUSDT/5m are examples. The bot reads the
existing rule's accepted `DI_TURNING_POINT_V3` BUY/SELL rows, bounded by the
matching committed rule checkpoint. It joins the same pair's canonical candle
close times, so monthly candles and gaps do not use guessed durations. WAIT,
WARMUP, SUPPRESSED, unrelated triggers and uncommitted future rows do not execute.
It does not calculate features, write ADCN, activate markets or backfill history.
If the live rule has not committed a current checkpoint, creation reports that
it is waiting instead of inventing a strategy or signal.

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

## Waiting, quote errors and pipeline health

`python3 -m Section_15_Execution_Bot diagnose ena-5m` performs a bounded read-only
check of the paper account, last successful quote receipt, latest closed raw
candle, feature checkpoint, decision checkpoint and latest accepted signal in the
last 24 hours. It makes no network requests, does not recalculate the strategy,
and cannot create a missing ledger. It distinguishes `WAITING_FOR_NEW_CONFIRMED_BUY`
from `DECISION_WORKER_BEHIND`, `FEATURE_WORKER_BEHIND`, `MARKET_DATA_STALE`,
`QUOTE_UNAVAILABLE_OR_STALE`, and `STRATEGY_FEED_UNAVAILABLE`. All timestamps are
milliseconds since Unix epoch; ages and lag are seconds. The worker's `Watching`
label alone is not proof that upstream calculations are current.

By default, `run` prints fills, changes in errors and recovery immediately, plus a
heartbeat every 30 seconds. `--heartbeat-seconds N` changes only console frequency,
not polling or stop evaluation. `--verbose` restores every-turn output; `--once`
always prints its single turn. Handshake/read timeouts or requests taking more
than five seconds still produce no fill; the loop tries again on its next turn.
No stale cached quote is substituted. Protective exits require a successful fresh
quote and therefore cannot be guaranteed to trigger during a network outage.

After upgrading worker code, stop/restart only `run`. Do not recreate the allocation
or run `enable` again merely to restart: its balance, position, consumed-signal
cursor and activation time already persist in the private ledger.
