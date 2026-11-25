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

There is **one bot and one shared simulated USDT wallet per ledger**. Named
coin/timeframe allocations are strategy slots, not separately funded accounts.
Each slot owns its position and history. A BUY uses the smaller of shared available
cash and that slot's entry cap, including modeled entry fees. SELL returns net
proceeds to the same pool. Profits compound across the bot. SQLite transactions
prevent concurrent slots from spending the same cash twice. A slot cannot short
or sell another slot's position. Slots with no available cash skip the BUY and
require a new confirmed BUY after funds become available; old signals are not queued.
When signals compete, the worker's existing slot iteration order determines which
slot receives funds first. This release does not implement portfolio rebalancing.
Adding a slot never adds, resets or duplicates starting funds.

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

`--capital` initializes the shared wallet **once**. When adding further slots, omit
`--capital`; configure only their entry caps and exits. The CLI rejects another
starting deposit into an existing wallet. Coin and timeframe remain configurable; ENAUSDT/5m are examples. The bot reads the
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
`~/.tradingindicator/paper-bot.sqlite3`. `status` returns one top-level `wallet` plus slot configurations,
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
exchange reconciliation, exchange-native protection,
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

## Independent bot dashboard

Run `python3 -m Section_15_Execution_Bot dashboard` in a **second Terminal** while the
paper worker continues running. Open `http://127.0.0.1:8002/`. `--port PORT` selects
another free local port. The global `--db PATH` option selects the same private
ledger for either command; the default displays your existing `ena-5m` allocation.
The dashboard does not install/start/stop workers, fetch chart history, activate
markets, change the strategy, or bind to external interfaces. No chart server or
market-runner restart is required. It is a separate loopback-only web page, with
no real-order or API-key controls.

The four summary cards show the whole bot's shared cash, total equity, realized
and unrealized P&L, regardless of the selected slot. Position, exits and history
below them belong to the selected slot. The page also shows last
bid/ask and quote age, open position, current exits, last 100 fills, and signal-path
diagnostics. Stale quote estimates are labeled as last observed, not live equity.
Quote/activity timestamps show observations from the separate worker; the web
server being available alone does not establish worker liveness. Read-only state
polls use the private ledger; pipeline diagnostics are bounded read-only queries.
No exchange requests occur during these reads.

- **Pause entries** prevents new BUY entries while keeping protective/strategy
  exits active in a running worker. **Resume entries** validates the existing
  source and starts with fresh signals. Repeated resume requests do not move the
  activation time again.
- **Edit settings** is enabled only while paused and flat. It changes the entry
  cap, stop/take-profit, modeled fees/slippage and maximum signal age, preserving
  cash, history, cursor and P&L. The cap can be below the wallet balance: the rest
  remains reserve. Changes are audited in the private `configuration_changes`
  table, and stale browser edits are rejected.
- **New allocation** configures another coin/timeframe with the current strategy;
  creation starts paused and draws from the existing shared wallet. Starting
  capital appears only when initializing the first slot. Pair and strategy of an
  existing slot are immutable so its records cannot be repurposed accidentally.
- **Close paper position** explicitly obtains a fresh public quote, simulates the
  exit with modeled fees/slippage, and pauses entries in one ledger transaction.
  A stale position preview cannot close a different/new position. If quotes are
  unavailable, it leaves the position unchanged and reports an error.

After installing this version, restart the **paper worker** once before using the
dashboard. Do not recreate or re-enable existing accounts. This loads the updated
configuration validation and bid/ask reporting while retaining existing balances,
positions and signals. Thereafter the worker reads permitted settings changes on
its next turn; no worker restart is required for those edits. Stopping the web
server does not stop a separately running worker.

HTTP controls require the local Host/origin and a session token, and the dashboard
accepts JSON actions only. It intentionally has no remote/mobile exposure or
shared chart-login integration. Refresh the page if its server was restarted and
the dashboard session expired.

## Upgrading from separate paper wallets

Stop **both the paper worker and bot dashboard** before installing this update;
restart them using the updated code. Do not recreate or re-enable the existing
ENA slot. Chart and market runner processes do not need restarting.

A ledger with one legacy allocation migrates automatically at startup. Its exact
cash, position, cost, realized P&L, activation time, cursor and fills are preserved.
The original allocation records are retained in `wallet_migrations` for audit.
The wallet is stored once in `bot_wallet`; slot records no longer contain cash.
For compatibility, read-only account reports still expose `state.cash` with
`cash_scope: shared_bot_wallet`: it is the same pool, **never sum those aliases**.
The top-level `wallet` is authoritative. Slot `realized_pnl` remains attribution;
the wallet's realized P&L is the aggregate.

If multiple old wallets exist, automatic conversion stops without changing their
balances or positions. With old paper processes stopped, review them first:

```bash
python3 -m Section_15_Execution_Bot migrate-wallet
```

Only if preserving their **combined existing** cash and positions is intended:

```bash
python3 -m Section_15_Execution_Bot migrate-wallet --combine-existing
```

This consolidates their existing funds once; it does not create a new deposit or
reset histories. It also combines their original starting-capital totals for the
audit. Repeating it cannot add funds. A later legacy-writer record is rejected
instead of silently granting another balance. Do not run old worker code against
an upgraded ledger. The simulation still has no real-order capability.

## Automatic macOS login services and desktop shortcut

One-time setup: stop the manually launched **paper worker and bot dashboard** with
Ctrl+C, leaving the market runner and chart running, then run from your checkout
with its virtual environment active:

```bash
python3 -m Section_15_Execution_Bot services install
```

This installs and starts two user LaunchAgents: `com.tradingindicator.paperbot`
and `com.tradingindicator.paperbotdashboard`. Both use this checkout, its current
Python interpreter, and the same paper ledger. They start at login and restart
after exit/crash, with a 30-second throttle. They never import the worker into the
market runner's calculation loop. A per-ledger process lock rejects duplicate
paper workers. Stop manual processes before installation to free dashboard port 8002.

Double-click **Paper Bot Dashboard.webloc** on your Desktop, or visit
`http://127.0.0.1:8002/` in your browser. Closing that page does not stop the worker.
The shortcut uses your default browser. No Terminal needs to stay open.

```bash
python3 -m Section_15_Execution_Bot services status
python3 -m Section_15_Execution_Bot services uninstall
```

Status reports registered jobs and their current PIDs. Uninstall stops only these
paper services and removes their LaunchAgent files, retaining the ledger, history,
logs and shortcut. Installation refuses to overwrite service files belonging to
another checkout or ledger. It does not modify the chart or market-runner service.
Logs are in `~/Library/Logs/TradingBotV1/com.tradingindicator.paperbot*.log`.
Re-run `services install` after paper code updates to load the updated code.

The worker uses `caffeinate -i` to prevent idle sleep while running. Shutdown,
logout, forced sleep and network outages still interrupt it; login services are
not an always-on remote host. No paper fills/protective exits run while offline.
These services perform only paper simulation and do not submit real orders.
