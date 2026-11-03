# Momentum v1 experimental specification

One pure Section 5 engine consuming existing Section 4 measurements. No trend,
pivot or BUY/SELL calculation is replaced. No new Section 4 feature is required.

Price family: .75 × clipped(momentum_atr / 2) + .25 × clipped(ROC percent / 1).
Oscillator family: (RSI−50)/50. DI family: existing signed normalized dominance.
Price-linked anchor families use existing signed-spread changes from confirmed
price highs/lows, clipped after division by 10 DI points. Each anchor requires
valid source continuity and origin<=known<=as_of; missing anchors are not neutral.

Direction score: .50 price + .20 RSI + .15 DI + .075 high anchor + .075 low anchor.
MACD is disabled by default. If enabled, .10 moves from price to the existing
histogram/current ATR family, clipped after normalization by .1 ATR. Missing an
enabled MACD measurement leaves its budget unavailable; never renormalize.

Entry/hold deadbands .15/.075 and three closed-candle confirmations. The price
family must support a bullish/bearish proposal or hold; oscillators/anchors alone
cannot create movement direction in a flat price series. Direction and strength
remain independent. Strength uses .65 abs(price), .20 abs(RSI), .15 abs(DI);
with MACD enabled price becomes .55 and MACD gets .10. Required missing strength
inputs yield unavailable strength. Bands: <25 weak, [25,50) moderate, [50,75)
strong, >=75 very strong. Parameters are in immutable MomentumConfig.

Acceleration comes from the existing `momentum_strength_change` (change of
absolute ATR-normalized displacement), not its signed derivative. >=+.05 ATR:
accelerating; <=−.05: decelerating; otherwise stable. Thus a bearish impulse
becoming more negative can accelerate. Missing change -> unknown acceleration.

A confirmed directional acceleration is building; stable is sustaining;
deceleration is weakening. Exhausting requires three consecutive decelerating
observations AND corroboration from an opposing existing RSI divergence or a
qualified confirmed DI turn (DI+ or signed-spread high for bullish exhaustion;
DI− high or signed-spread low for bearish exhaustion). A DI turn is retained for
at most five subsequent closed candles. No overbought/oversold value alone proves
exhaustion. A pending/unknown/neutral direction has unknown condition.

The existing `di_anchor_events` channel supplies all six DI-extrema types without
a second detector. Only qualified events confirmed at this candle close, with an
older origin, are admitted. Original source timestamps/channel/value are retained;
source events without IDs get a deterministic reference hash, explicitly a
reference to the original payload, not a new pivot identity. Price-reference
events in that mixed channel are not mistaken for DI turns.

Coverage is the fixed directional family budget (.50/.20/.15/.075/.075, or
.40/.10/.20/.15/.075/.075 with optional MACD). Confidence is the sum of available
families' agreement with the proposal times confirmation progress; missing budgets
never inflate other contributions. It is rule evidence, not win probability.
Source units, bounds, times, continuity and feature window compatibility are
checked. Gaps reset confirmation and retained corroboration; loss of DI-anchor continuity
also clears retained DI-turn corroboration; previews return the
unchanged committed state. State is bounded; indicators stay in Section 4.

Core uses the existing runner, versioned history, immutable projected inputs and
atomic checkpoints. Momentum has no analytical-engine dependency. It shares the
current row/time budgets with Regime, Structure and Trend. UI, decisions, Section 9
confidence and Section 10 opportunity are unchanged. These hypotheses require
real-data diagnostics/calibration before any predictive or profitability claim.
