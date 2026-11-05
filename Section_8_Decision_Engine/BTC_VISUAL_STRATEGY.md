# BTC event-sequence strategy v0.2

This is a chart-visible spot simulation, not a production strategy or exchange
execution bot. Existing Section 8 decisions, notifications, runner scheduling and
Section 4 calculations are unchanged. No new database or historical replay is
required. The standalone build already includes Section 8 and these UI assets.

After updating and restarting the UI backend, choose BTCUSDT and 5m, 15m, 30m or
1h. Check **BTC strategy flags · experimental spot** in the main toolbar.
The checkbox and selected period are remembered in this browser across reloads.
A chart status explains when the layer is off, unsupported or awaiting data. Purple diamonds label BUY/SELL SETUP; cyan checks label later price
confirmation. Cyan dots show simulated buys and amber dots show exits.
**BTC events** opens a UTC event table with independent DI peaks/troughs, setup,
confirmation and cancellation records. Candidate updates no longer create markers. Cyan lines show entry, red lines hard stop, amber lines active stop (these
overlap until trailing activates). Turn the checkbox off to hide the layer.

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

## Event rules

1. Independently detect DI+ and DI- peaks and troughs from three contiguous closed
   candles. A strict peak is before < peak > after; a trough is the reverse.
   Plateaus are not guessed. The event is known only at the third candle close,
   with the middle candle recorded separately as its origin. Neither DI needs to
   mirror or turn alongside the other.
2. When flat, a DI- peak creates a BUY setup only if DI- dominates at both the peak
   and its detection. While holding BTC, the equivalent dominant DI+ peak creates
   a SELL setup. Ties are neutral. Dominance chooses the opportunity side, not an
   immediate order. Protective exits are always allowed.
3. Price must confirm on a **later** closed candle: above the setup-detection
   candle's high for BUY; below its low for SELL. The opposite DI does not have to
   improve on this candle. Recognition and confirmation cannot share a candle.
4. Confirmation must arrive within eight later candles with the same dominance
   gate. A gate change cancels the setup. BUY invalidates below the lowest price
   of the three peak-detection candles; SELL invalidates above their highest.
   A later valid peak can create a fresh setup after cancellation.
5. Buy or exit at the following candle OPEN, with adverse slippage. BUY rejects an
   opening at/below the setup low or over 0.5% above confirmation close. There are
   no shorts, sell orders while flat, or multiple simultaneous positions per TF.
6. Candidate high/low is an optional confluence snapshot at setup/confirmation.
   Adding, deleting or moving candidates cannot create a setup, confirm it,
   invalidate it or change a fill. The initial candidate-driven rule is removed.

Every DI turn records its three values, origin and knowledge times, dominance,
absolute spread and each DI's relation to that spread. Spread is measured context,
not an assumed 35-point trading threshold. These later price-confirmation and
expiry parameters are explicit initial hypotheses, not validated BTC constants.

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
  --before 2026-11-05T00:00:00Z --output btc_di_sequence_review.json
```

This uses the same read-only simulation as the chart. The summary covers the full
selected history; detailed events and trades are the recent chart tail. Closed
trades alone contribute to mean net return. Open and censored trades are counted
separately. It makes no prediction or profitability claim. Share the report to
review the November 4 00:45 UTC area against the recorded sequence.
