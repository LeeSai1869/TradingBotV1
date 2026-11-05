# BTC controlled-event strategy v0.4

This is a chart-visible spot simulation, not a production strategy or exchange
execution bot. Existing Section 8 decisions, notifications, runner scheduling and
Section 4 calculations are unchanged. No new database or historical replay is
required. The standalone build already includes Section 8 and these UI assets.

After updating and restarting the UI backend, choose BTCUSDT and 5m, 15m, 30m or
1h. Check **BTC strategy flags · experimental spot** in the main toolbar.
The checkbox and selected period are remembered in this browser across reloads.
A chart status explains when the layer is off, unsupported or awaiting data.
Cyan checks label BUY DI CONFIRMED on the third detection candle; cyan dots
show simulated buys and amber dots show exits with S2/S3/TS/SL reason tags.
Early sell setups arm the trailing line rather than creating a direct sell. A confirmed DI event is known only
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
   detection. Ties are neutral. Entry rules are unchanged from v0.3. Selling uses
   the separate scenario rules below; a DI+ peak no longer directly sells.
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

## Controlled sell catalogue

| ID | Applicable situation | Event and action |
| --- | --- | --- |
| S1_EARLY_SELL_TRAIL | Holding BTC; dominant DI+ peak at origin and detection | EARLY_SELL_SETUP arms trailing only. It never directly sells. |
| S2_BULLISH_SPREAD_MATURITY | Holding BTC; DI+ dominates and absolute spread is strictly above 40 | Latch maturity. The first subsequent strict decrease versus the previous closed bar schedules an exit at the next open. |
| S3_EMERGING_BUYER_CONTROL_LOSS | At buy eligibility, DI+ was below both DI- and absolute spread | Wait until DI+ gains control, then exit on a later DI-/spread crossover from below DI+ to above it. |

S2 ignores large bearish spreads. Exactly 40 does not arm maturity; an unchanged
spread is not a decrease. Once matured, no extra three-candle peak is needed.
For S3, still being below both lines just after entry is not a crossover. An entry
with DI+ below DI- but above/equal to spread is a different scenario: S3 does not
apply. Snapshot uses the known buy-signal close, never the future entry-bar close.
With absolute spread, DI- must cross DI+ before spread can cross it after bullish
control. Both line events are recorded without pretending they are independent.

All matching evidence is retained. If S2 and S3 match together, S2 has explicit
priority. Protective gap stops execute before a pending signal exit. Sells do not
open shorts or sell when flat. No universal DI+ peak sell remains.

### Independent protection

Hard stop is 0.5% below entry and always active. Gaps/slippage/fees can exceed that
price threshold. Trailing now activates ONLY when S1 detects the early sell setup,
not when profit reaches 0.5%. Once armed, it stays armed until exit, regardless of
later DI recovery or setup invalidation. Each closed candle ratchets the stop up
to the high-water price minus 1.5 ATR, never below the existing stop/hard stop,
and never above the current close. It does not automatically jump to breakeven.
The updated level first applies to the NEXT candle; current high/low cannot
retroactively generate a favorable fill. Stop hits use the existing intrabar
model and adverse slippage. Price-based stops remain independent of DI gates.

Missing data censors open trades without assigning profit. The unfinished tail
stays OPEN. Assumed per-side costs remain fee 4 bps plus slippage 2 bps.

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
  --before 2026-11-05T00:00:00Z --output btc_controlled_v04_review.json
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

## One-rule-at-a-time comparisons

The report includes a sell-rule manifest (ID, scenario, enabled state and action),
full per-trade exit reasons, and matched rule IDs. Chart events show Rule and
Action separately. Run the same fixed period with one rule disabled, for example:

```sh
python3 inspect_btc_strategy.py --timeframe 15m --days 90 \
  --before 2026-11-05T00:00:00Z \
  --disable-sell-rule S2_BULLISH_SPREAD_MATURITY \
  --output btc_v04_without_S2.json
```

The option is repeatable. Disabling S1 disables arming its trailing stop; it does
not change entries or hard stops. The main chart uses all three enabled rules.
Previous version reports remain unchanged. New rules change position duration
and therefore later entries; compare complete reruns, not shifted old trades.
Learned DI boundaries and an ATR breakout/crash override are still deferred.
Candidate-high confluence is recorded but no unagreed candidate gate is added.
