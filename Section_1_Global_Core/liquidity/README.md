# Observed perpetual liquidity

This is live Binance **USDT-margined perpetual** order-book data, separate from
spot candles and from the existing Pine candle-derived liquidity levels. It
starts collecting now; it does not create synthetic book history or change
feature formula signatures/checkpoints. Existing inferred indicators remain
internal compatibility inputs, not order-book observations.

## Start on macOS

```sh
python3 -m pip install -r requirements-liquidity.txt
python3 restart_liquidity.py
python3 restart_ui.py
```

The independent `com.tradingindicator.liquidity` LaunchAgent runs at login,
including when the UI is closed. Its own process/file lock prevents duplicate
writers in one checkout. It stops collecting during sleep, shutdown, network
outages or a symbol pause. Candle downloads/replays use their existing runner.
On other platforms, run `python3 -m Section_1_Global_Core.liquidity.runner`.
An optional `--symbols BTCUSDT ETHUSDT` limits collection to those enabled coins.
Default collection covers up to 50 enabled symbols that exchange discovery
confirms as trading USDT perpetuals. It never aliases a spot symbol to a different
contract, or includes dated/coin-margined futures under the same identity.

Enable **Settings → Features → Liquidity → Select all**. Bids, asks and history
have separate visibility/opacity controls. The chart shows current side bars,
a recent heatmap, hover amounts/time and an expandable price-band table. Values
are quote **USDT**, not USD conversions. The badge explicitly identifies the
perpetual feed and the existing spot candles. A missing or stale book is hidden;
known historical samples can remain at their actual observation times. Current
bands are not projected onto an unrelated historical chart viewport.

Check `python3 liquidity_status.py BTCUSDT`. Logs are
`~/Library/Logs/TradingBotV1/liquidity.log` and `liquidity-error.log`.
Disabling a display does not stop recording; pause its coin in the existing
policy, or unload this separate LaunchAgent to stop the recorder altogether.
No API key or third-party liquidity service is used.

## Source and integrity

The adapter uses the public USD-M endpoints:

- REST `https://fapi.binance.com/fapi/v1/exchangeInfo`, `/fapi/v1/depth?limit=1000`,
  and `/fapi/v1/openInterest`.
- Combined stream `wss://fstream.binance.com/stream?streams=...` with per-symbol
  `depth@100ms`, `aggTrade`, `forceOrder`, and `markPrice@1s` subscriptions.
- Protocol reference: [local book synchronization](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly).

Connect and buffer depth **before** fetching the snapshot. Discard updates with
`u < lastUpdateId`; bridge using `U <= lastUpdateId <= u`; subsequent events must
have `pu == previous u`. Quantities replace prior quantities; zero removes a
level. Sequence gaps, missing bridges, crossed/empty books, stale or delayed
exchange updates and queue overflow end that session and require a new snapshot.
Buffered old data is not made live merely by receiving it after a laptop wakes.
Reconnection gaps are recorded, not forward-filled.

A snapshot is limited to 1,000 levels per side. Only prices within its initial
outer boundaries are trusted; isolated updates outside them cannot establish
complete coverage. Cumulative depth at a distance is null when that distance
exceeds known coverage. A stable logarithmic 10-bps grid groups observed orders
within 100 bps of mid. Orders can be withdrawn; displayed depth is not guaranteed
execution or hidden liquidity.

The implementation and recovery tests use local protocol fixtures. This build
environment's proxy blocked Binance documentation and public API access (HTTP
403 tunnel failure), so **production REST/WebSocket connectivity has not been
validated here**. Startup reports real discovery/connection failures explicitly;
it does not fall back to candle estimates. Exchange access/protocol compatibility
must be confirmed using the recorder status on the deployment machine.

## Stored features and training

Every healthy publication (about five seconds) contains:

- Best bid/ask, mid, spread and transport delay.
- Bid/ask USDT depth and imbalance at 5/10/25/50/100 bps; missing coverage is null.
- Estimated market-buy/sell slippage for 1k/10k/100k USDT relative to mid, including
  spread and excluding fees. Insufficient known depth yields null.
- Displayed notional additions/removals since synchronization. **Removals are not
  identified as cancellations**: fills can remove displayed quantity too.
- Sampled band persistence and changes in near-mid depth. Persistence means
  presence at consecutive publications, not proof that the same orders stayed.
- Aggressive buy/sell aggregate-trade notional over the publication window,
  with sequence continuity/partial coverage. Buyer-is-maker means aggressive sell.
- Reported last-filled liquidation notional: SELL is long liquidation, BUY is
  short liquidation. The force-order stream is sampled and **not an exhaustive
  liquidation total or a map of open positions/liquidation prices**.
- Latest mark/index price, funding rate/next funding time, and open interest.
  OI is polled about once per minute and nulled after two minutes without a
  refresh; mark/funding context is nulled after ten seconds. Source/receipt times
  accompany it. Open interest is in the exchange's instrument units, not USD.

A new closed-minute summary is committed when the next healthy minute is
observed. Means and sampled trade-flow sums include coverage; no missing minute
is fabricated. An outage can delay finalization and leaves incomplete coverage.
This summary is a separate liquidity record, not a retroactive spot feature.

Read through the public Core gateway:

```python
from Section_1_Global_Core.global_packet import read_liquidity, read_liquidity_candle
sample = read_liquidity('BTCUSDT', decision_time_ms)
minute = read_liquidity_candle('BTCUSDT', minute_open_ms, decision_time_ms)
```

Reads require `available_ms <= decision_time_ms`; stale samples and samples
crossed by a recorded gap are rejected. Exchange event, receipt, sampling and
storage-ingestion timestamps are distinct. Venue/market/symbol identity is
always explicit. Do not use later-arriving samples or partial-coverage minutes
as if they were known at the candle open. These are observations, not direction
probabilities; no prediction model or leverage/liquidation-position estimates
are invented from the order book.

## Resource boundaries

Separate SQLite WAL memory lives in
`memory_storage/Storage/liquidity/liquidity.db`. Five-second samples retain six
hours; the UI requests at most 240 (roughly the latest 20 minutes). Minute
summaries retain 90 days and gap records seven days. Compression keeps packet
storage bounded; ordinary retention deletes rows, not old candle/feature data.

Raw stream events, snapshots and OI responses are compressed JSONL (not Parquet),
partitioned by venue/market/symbol/UTC date and rotated in approximately 10-MiB
chunks. Closed owned chunks are trimmed after seven days or around a 2-GiB
budget, whichever applies first. Open chunks can temporarily exceed that budget.
Only this recorder's `.jsonl.gz` files are pruned. Raw retention can be much
shorter on busy markets. Export records before retention if training needs them.

The writer has bounded queues (20k raw events, 1k control/publication items),
at most 64 archive handles, two snapshot workers and two context workers. Raw
queue overflow forces resynchronization and an explicit coverage gap. A storage
failure stops collection rather than silently claiming complete data. REST
requests share a one-per-second start limit, honor 418/429 cooldowns, and do not
block WebSocket reads. None of these workers runs in the UI request path or
shares the candle runner's writer lock. Validate CPU/disk/network usage before
assuming 50 busy instruments can be retained without gaps on a laptop.
