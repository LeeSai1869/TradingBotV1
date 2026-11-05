# BTC visual strategy v0.1

This is a chart-visible spot simulation, not a production strategy or exchange
execution bot. Existing Section 8 decisions, notifications, runner scheduling and
Section 4 calculations are unchanged. No new database or historical replay is
required. The standalone build already includes Section 8 and these UI assets.

After updating and restarting the UI backend, choose BTCUSDT and 5m, 15m, 30m or
1h. Check **BTC strategy flags · experimental spot** in the main toolbar.
The checkbox and selected period are remembered in this browser across reloads.
A chart status explains when the layer is off, unsupported or awaiting data. Purple diamonds mark
candidate-low observations, cyan markers show simulated buys, amber markers show
exits. Cyan lines show entry, red lines hard stop, amber lines active stop (these
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

Initial hypothesis: a candidate low arms a setup. Within eight candles, a close
above the previous candle high with DI- declining and DI+ increasing arms an entry
at the next open. A lower candidate resets the setup. A broken low cancels it.
Gap/chase entries beyond 0.5% of the trigger close are rejected. Each observed
anchor can arm one entry in the evaluated window. There are no short positions.

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
