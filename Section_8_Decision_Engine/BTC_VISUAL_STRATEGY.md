# BTC DI-turn strategy v0.3

This is a chart-visible spot simulation, not a production strategy or exchange
execution bot. Existing Section 8 decisions, notifications, runner scheduling and
Section 4 calculations are unchanged. No new database or historical replay is
required. The standalone build already includes Section 8 and these UI assets.

After updating and restarting the UI backend, choose BTCUSDT and 5m, 15m, 30m or
1h. Check **BTC strategy flags · experimental spot** in the main toolbar.
The checkbox and selected period are remembered in this browser across reloads.
A chart status explains when the layer is off, unsupported or awaiting data.
Cyan checks label BUY/SELL DI CONFIRMED on the third detection candle; cyan dots
show simulated buys and amber dots show exits. A confirmed DI event is known only
at that candle close; the fill uses the next open. No extra price-confirmation
candle is needed. **BTC events** opens the UTC DI event table. Candidate updates
create no markers. Cyan lines show entry, red lines hard stop and amber lines
active trailing stop. Turn the checkbox off to hide the layer.

Choose 7, 30, 90 or 365 days beside the checkbox (default 90). Each selected
timeframe is simulated independently over committed, closed candles in that
period: about 25,920 bars for 90 days of 5m history, or 105,120 for 365 days.
Only the latest 1,000 candles worth of drawing data is returned to the chart;
simulated positions carry forward from the earlier history. Selecting a longer
period does not download missing history or recalculate features. Actual coverage
is displayed and depends on the committed feature checkpoint.

It starts flat at the evaluation history boundary. The sliding window can
therefore exclude positions originating earlier; it is not persistent live
position accounting. Historical chart mode evaluates through the displayed last
closed candle. Source feature replay or invalid signatures produce an explicit
unavailable message, not fallback classifications. Close-time feature availability
is reconstructed, not proof of actual historical publication time.

## Clean DI rules (v0.3)

1. Independently detect DI+ and DI- peaks and troughs from three contiguous closed
   candles. A strict peak is before < peak > after; a trough is the reverse.
   Plateaus are not guessed. The event is known at the third candle close, with
   the middle candle recorded as its origin. DI lines need not mirror or turn
   alongside one another; events and candidates can share a candle.
2. When flat, a DI- peak is BUY eligible if DI- dominates at both the peak and its
   detection. While holding BTC, a dominant DI+ peak is SELL eligible. Ties are
   neutral. This is a broad reversal hypothesis, not proof of a price bottom/top.
3. Fill at the following candle OPEN with adverse slippage. There is no additional
   price gate, requirement for a later candle, setup expiry, prior-low entry
   rejection or 0.5% chase rejection. Risk protection remains distinct from the
   signal rule. No shorts, sells while flat or simultaneous positions per TF.
4. Price close/high/low, whether the close crossed the preceding high/low, and
   candidate pivots are confluence snapshots only. They cannot enable, block or
   delay a DI event. They do not yet modify holding/exits; that interpretation is
   a later step after reviewing this clean baseline.
5. Spread and each DI's relation to it are recorded context, not an assumed
   35-point threshold. Trend/regime, RSI and other gates are not added here.
6. An ATR breakout/crash override is explicitly DEFERRED. Existing ATR-based
   trailing protection is retained; it is not a breakout/crash override.

V0.2's later-price-close gate was an extra restriction, not part of the requested
DI concept. V0.2 reports remain archived unchanged for comparison. A 03:15
15-minute detection candle can first yield a confirmed signal at 03:30; v0.3
can fill at that open if the DI gate qualifies and the simulated position is flat.
It cannot retrospectively fill at 03:15 using that candle's closing DI values.
Position state and earlier trades can change after removing the price gate, so
specific old trades cannot simply be shifted backward and called a new backtest.

Hard stop: entry price minus 0.5%, effective immediately after entry. A gap below
it fills at the worse opening price. This is a price threshold; realized loss can
exceed 0.5% because of gaps, slippage and fees. A close at least 0.5% above entry
activates a monotonic 1.5 ATR trail with a cost-aware breakeven floor. This is not
a fixed profit exit. Close-updated stops apply only to subsequent candles; current
candle highs cannot retroactively stop a trade at a favorable price. Missing data
censors open trades without assigning profit. An unfinished tail position stays
OPEN. Assumptions: fee 4 bps and adverse slippage 2 bps per side.

Still to evaluate: inherited/emerging DI dominance, upper candidate exhaustion,
weak-market profit exits, support-zone filters, trend/regime contexts and confidence
buckets. Existing confidence is evidence quality, not win probability. The initial
rules and costs are hypotheses, not calibrated BTC parameters. No profitability
claim has been made. Production history is on the user's laptop, not this workspace.

Read-only API: `/api/strategy/btc?symbol=BTCUSDT&interval=5m`, optionally `days` (7/30/90/365) and `before`
(UTC milliseconds, exclusive close boundary). It uses existing API authentication.
The overlay requests again when the last displayed closed candle or selected
horizon changes, with a maximum frequency of once per 15 seconds, and receives no live
exchange ticks. No request is made while disabled or on unsupported symbols.

Validation: unit tests cover next-open fills, gap stops/costs, nonretroactive trails,
DI-only rejection and censored gaps; stored-source tests cover closed cutoffs,
read-only access and replay guards; browser test renders the actual chart primitive
and checks the toggle, symbol scope, polling and unchanged autoscale.

## Local review command

```sh
python3 inspect_btc_strategy.py --timeframe 15m --days 90 \
  --before 2026-11-05T00:00:00Z --output btc_di_only_v03_review.json
```

This uses the same read-only simulation as the chart. The summary and complete trade list cover the full
selected history; event and stop-level details remain the recent chart tail. Closed
trades alone contribute to mean net return. Open and censored trades are counted
separately. It makes no prediction or profitability claim. Share the report to
review the November 4 00:45 UTC area against the recorded sequence.

The summary includes a simulated $100 balance compounded through all closed
trades with fractional position sizing and the stated costs. Open/censored trades
are excluded and are counted separately; this is not a marked-to-market account
balance. There is no exchange lot-size rounding, minimum-notional model or claim
of executable live returns.
