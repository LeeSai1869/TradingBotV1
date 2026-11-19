# User strategy-testing constraints

Confirmed 13 November 2026 (Asia/Karachi): spot strategies have an intended
maximum loss of 0.5% on every entry. Every primary replay must include a hard
protective stop from entry; do not headline results for an unlimited-loss or
24-hour mark-to-market policy as the user's trading strategy.

User cost correction: **0.2% total per completed round trip**, including the
entire cost allowance. Use the stated arithmetic for current comparisons:
net return = gross chart-price return minus 0.2 percentage points. Thus 0.5%
gross gives 0.3% net; 1% gross gives 0.8% net. Do not add further assumed fees
or slippage on top. With a 0.5% intended net-loss budget, the initial price
stop is 0.3% below entry; a 0.5% price stop would exceed that net-loss limit.
Retain actual adverse opening gaps. Older frozen reports used a different
cost model and remain historical evidence, not the current assumption.
The corrected comparison is in
[the 20 bps cost report](../reports/DI50_breakout_exit_routing_cost20bps/README.md).

The BTC 1h DI-spread reversal hypothesis buys after the first spread decline
from a local peak above 40, comparing DI− thresholds 40, 45 and 50 and showing
RSI <20 as an explicit optional condition and its timing. Counts must distinguish
raw setups, filters, eligible entries, overlapping positions and missing data.

Latest revision: **bearish Regime exits directly at the 1% profit target**.
This replaces the earlier bearish trailing-activation instruction. In bullish
Regime, keep activation at **profit ≥1% AND DI+ >50** (explicitly confirmed by
the user). Once activated, the bullish stop follows 0.5% below the highest
observed price since BUY. Keep the initial hard stop active before activation
and never disarm an activated trail. There is no fixed 24-hour exit.

The user subsequently proposed confirming the forming 1h setup on the 5m chart.
The current research interpretation is a causally confirmed **5m DI-spread high
and first decline**, as confluence for the forming-hour DI extreme/turn. Report
this interpretation explicitly; do not replace it with a future price pivot.

The latest research task also requires causal breakout and crash detection to
improve entry execution. Audit the unexpectedly low winning ratio independently;
do not change outcome labels or omit stops to manufacture a higher win rate.

Report the effects of costs explicitly: a 0.5% price stop and a 0.5% net-loss
budget are different. Include the cost-adjusted budget scenario and retain any
modeled gap/slippage breach rather than clipping losses to force the limit.
Profit activation measured as net return versus price appreciation must also be
labelled. Neutral/unknown regime treatment and current versus entry regime are
research assumptions, not silently inferred user instructions.

Latest entry refinement (14 November 2026): on the 15m study, require bearish
same-timeframe Trend and simultaneous strict DI− and absolute DI-spread peaks
above 50: value[2] < value[1] and value[0] < value[1]. DI+ reverses these
inequalities, forming a trough: DI+[2] > DI+[1] and DI+[0] > DI+[1]. No RSI
condition was requested for this refinement. Compare thresholds at the peak
versus still above 50 on the confirmation candle explicitly. The literal
"DI+ did not decrease" alternative, DI+[0] >= DI+[1], is a separate
interpretation sensitivity, not a silent replacement for the strict trough.
Current/previous/two-ago mean closed candles 0/1/2. Entry is the next open.

Latest exit experiment (14 November 2026): retain these entries and compare
ordinary relief-bounce exits at **+0.5% and +1% gross chart-price gain**, versus
a trailing exit selected by breakout evidence observable before that target
fills. Keep the 0.5% initial net-loss budget. Do not select trailing using a
future extended-move label, remove stopped trades, or count later recovery as
an earlier win. Gross targets differ from the previous net-target reference.
The tested breakout branch arms at +1% gross and trails 0.5% below the highest
price since entry; this is an exploratory policy, not an enabled live rule.
Full definitions, identical entry cohorts, both intrabar paths and every exit
are in [the exit-routing report](../reports/DI50_breakout_exit_routing_v1/README.md).

The current fixed-bearish-target audit and breakout/crash definitions are in
[the v3 research report](../reports/BTC_1h_bear_target_breakouts_v3/README.md).

Use only information known at the decision time. Prefer recorded lower-timeframe
prices for stop/trailing execution. Missing data and OHLC ordering uncertainty
must remain visible. Research does not authorize changing live rules, deleting
features/ADCN memory, or sending orders.
