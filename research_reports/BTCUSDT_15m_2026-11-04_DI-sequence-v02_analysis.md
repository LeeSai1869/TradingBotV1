# BTCUSDT 15m — November 4, 2026 event-sequence review

Source: `BTCUSDT_15m_2026-11-04_DI-sequence-v02.json`, uploaded in commit
`32fa289a`. Rules: `btc-events-v0.2`, implemented in `037b0818`.
All times below are UTC. This is an analysis of the supplied simulation output,
not a fresh backtest against the production candle database.

## Finding: 00:45 is a setup, not an entry in v0.2

| Chart candle | Event becomes known | Recorded evidence |
| --- | --- | --- |
| 00:30 | 01:00, after the next candle closes | DI- peak origin: 42.4843, after 41.4650 and before 35.8325 |
| 00:45 | 01:00 | BUY SETUP; DI- 35.8325 versus DI+ 9.3864; spread 26.4461 |
| 01:00 | 01:15 | BUY CANCELLED: setup price invalidated |

The setup required a later close above **77,253.58**. Its frozen invalidation
level was **76,855.99**. The report records price invalidation on the 01:00
candle; therefore this sequence did not schedule or fill a buy. The report has
no v0.2 trade at 00:45 and no carried-in trade across midnight.

The three-candle DI- peak was a weakening-pressure observation, not sufficient
proof of a price bottom. Both DI lines were falling at detection: DI+ went from
11.1288 at the peak-origin candle to 9.3864 at detection. V0.2 does not require
opposite-DI confirmation, but the independent price requirement stopped this
particular setup from entering.

The original complaint predates v0.2. This report cannot establish the exact old
entry price, loss or old-rule cause; it contains the new strategy, not an export
of the older strategy or canonical production decisions. No missing raw OHLC,
RSI, ADX or one-/five-minute readings have been invented.

## Later recovery sequence

| Chart candle / fill | Event becomes known | Evidence / action |
| --- | --- | --- |
| 03:00 | 03:30 | New DI- peak origin: 46.7776, with 39.5199 before and 39.7072 after |
| 03:15 | 03:30 | BUY SETUP; later close must exceed 76,384.09; invalidation 75,736.38 |
| 03:45 | 04:00 | BUY CONFIRMED at close 76,496.04; DI- 31.5460 still dominates DI+ 13.5533 |
| 04:00 open | 04:00 | Simulated entry 76,511.34921 including adverse entry slippage |
| 11:45–12:00 candle | Intrabar time unavailable | Trailing exit, simulated fill 78,459.44110 |

Initial hard stop: **76,128.79246**. Final active trailing stop:
**78,475.13612**, with adverse exit slippage giving the lower fill above.
Net trade return: **+2.4641%**, after assumed per-side fee 4 bps and slippage
2 bps. Recorded high during the trade: **78,714.48**, or about **+2.8795%**
relative to the slippage-adjusted entry before exit costs. This is an observed
historical high, not a price the strategy was guaranteed to capture.

During the rise, SELL setups on the 04:15, 05:00, 06:00 and 07:30 candles were
subsequently cancelled by higher prices. They did not force exits merely because
DI+ dipped. The reported exit was a trailing stop. Exit timestamps in this file
identify candle opens; they do not establish the precise intrabar execution time.

## Full supplied 90-day summary

Coverage: August 7 00:00 through November 4 23:45 candle opens, 2026, UTC.
8,640 candles; no reset/gap events reported.

| Measurement | Reported value |
| --- | ---: |
| Entries / closed trades | 209 / 209 |
| Winning closed trades | 86 |
| Win rate | 41.15% |
| Mean net return per closed trade | -0.11236% |
| Open / censored trades | 0 / 0 |

The average remains negative under the assumed costs. A successful November 4
trade is not evidence that the strategy is ready for execution. The report only
retains 16 detailed recent trades; the aggregate summary covers all 209. The
recent tail must not be substituted for the full-period result. Full-period
profit factor, drawdown and chronological trade-by-trade comparisons cannot be
reconstructed from the truncated trade list alone.

## Next comparison

Keep these rules and this report unchanged as the v0.2 baseline. Before changing
a gate, export aligned raw candles/features plus complete trade histories for
the same fixed period. Compare a predefined change against this baseline,
including rejected recoveries as well as successful ones. One-/five-minute entry
timing requires those recorded timeframes; this report cannot test it.
