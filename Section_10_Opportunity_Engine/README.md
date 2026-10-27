# Conditional opportunity scenarios

Production entry point: `engine.evaluate(close, features, fee_bps=4,
slippage_bps=2)`. Legacy numbered files are retained as reference, not imported
by the active engine. The original three-layer concept and family deduplication
are retained. The asymmetric requirement for three above zones before assigning
a short risk boundary is not carried forward; one valid opposite barrier suffices.

For each side, known S/R, institutional S/R, FVG, OB, breaker, swing/protected
structure, volume profile/nodes, moving averages, VWAP, prior-day/session and
nearest Fibonacci levels form ordered price barriers. A cluster merges edges
within 0.15 ATR of its first edge, preventing transitive merging of distant
levels. Families are counted once per cluster. The nearest edge is the target,
not its center or the far edge. Up to three clusters are returned per side;
missing levels stay absent. A barrier is an obstacle, not a guaranteed destination.
There is no synthetic liquidation map or unobserved order-book target.

A structural opposite-side barrier sets scenario invalidation beyond its far
edge by 0.1 ATR. In its absence, 1.5 ATR is an explicitly labeled model fallback.
Risk is not an executed stop order. A gap can realize a worse fill. Price return
is directional: (target-entry)/entry for BUY and (entry-target)/entry for SELL.
Net return subtracts entry and target exit fees/slippage using their respective
notionals. Risk includes entry and invalidation exit costs. Reward/risk is net
reward divided by modeled cost-inclusive risk. Target 1 needs positive net reward
and at least 1.5R for the `favorable geometry` label; this is not expected profit.
The default per-side fee is 4 bps and slippage 2 bps, editable in settings.
Funding, taxes, borrow fees, sizing, leverage, fill probability and expected value
are not estimated. Prices can differ by venue/market; current perpetual depth is
not mixed into the app's spot-candle scenarios.

Settings > Features > Opportunity has six independent Display controls (T1–T3
for BUY and SELL), Style controls/cost assumptions and a Data breakdown. Enabled
scenarios draw horizontal target and invalidation lines without changing chart
scale or candle data. They describe the latest closed-bar entry, with its UTC
as-of time. They update on closed candles and are hidden while viewing older
history. They are not a frozen trade ledger or retrospective profitable trade.
Historical signal rows also receive their own immutable-input scenario values.

Calculations share the existing combined chart response, use bounded caches,
and never write to OHLCV/features/ADCN or trigger their replay. Cost settings are
validated server-side (finite 0–100 bps per side). Changes affect only the view.
