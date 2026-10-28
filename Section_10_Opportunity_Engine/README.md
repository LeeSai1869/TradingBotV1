# Opportunity bands tied to a price point (v2)

Production entry: `engine.evaluate(close, features, fee_bps=4, slippage_bps=2)`.
The engine calculates above/below areas from price inputs independently of BUY or
SELL decisions. Section 8 owns decisions. Core selects the latest decision's
price/time for the chart; Section 10 owns geometry and context tracking.

The old numbered reference files remain reference material. Version 2 restores
band geometry and their distance scales (1 ATR confluence, 2 ATR layer spacing,
3 ATR susceptible area), rather than treating each nearby point as a target line.
This is a reviewed implementation, not a claim of byte-for-byte legacy fidelity.

Real S/R, institutional, FVG, OB, breaker and volume-node ranges keep their bounds.
Overlapping ranges coalesce, including nested or chained real overlaps. Nearby
ranges merge only within bounded susceptible span. Point references (EMA, VWAP,
Fibonacci, swings and session levels) get explicitly modeled +/-0.1 ATR bands,
clipped to the correct side of entry. They are not observed liquidity zones.
The final selection enforces layer spacing; nearby references beyond the allowed
span are retained as enrichment metadata instead of separate congested layers.
Families count once. Up to three separated areas are returned; missing areas
are never invented simply to fill three slots.

Each band retains low/high, source families, whether geometry is modeled, and
net return/reward-risk at both its near and far edge. The existing `price` and
`net_reward_pct` fields retain the conservative near-edge values for compatibility.
The near edge is not an expected fill. The opposing side's nearest known band is
exposed separately as `opposing_band`: after SELL this is the upper potential
barrier; after BUY it is the lower potential barrier. It is not a promise that
price turns there. Scenario invalidation is separate: 0.1 ATR beyond a structural
opposite barrier, or a labeled 1.5 ATR model fallback. Fees/slippage apply at entry
and exit notionals; funding, taxes, leverage, sizing and fill probability are not
modeled. Default per-side assumptions remain 4 bps fee and 2 bps slippage.

Chart behavior:

- After BUY: upper potential take-profit areas, lower opposing area and risk.
- After SELL: lower potential buy-back areas, upper opposing area and risk.
- Filled bands, editable borders/opacity, optional labels and reference line.
- Labels are spaced with leaders; the underlying prices are never moved for fit.
- Completed, invalidated and ambiguous references stay displayed with their state
  until a newer decision replaces them. They are not silently presented as active.
- A raw/feature gap marks coverage unknown while retaining the known reference.
- The confusing unanchored-preview chart switch is removed; saved values migrate
  to anchored display. Data still exposes independent point calculations.

Two-candle polling sends the known `analysis_reference` timestamp in the existing
combined chart request. Core verifies it using the canonical DI projection,
reconstructs its source features, and advances at most 10,000 raw candles. It
never scans full feature history or stores duplicate feature rows. If coverage
cannot be established, reference validity is labeled unknown. Two extra seed
candles handle anchors at a short page's lookback boundary. Neither the browser
nor opportunity engine invents or filters a decision to obtain an anchor.

Core's public `evaluate_price_point(client, features, previous)` remains usable
without any decision input. `inspect_price_point.py` now requests context history
explicitly so a WAIT row doesn't misleadingly print a null anchor solely because
normal chart responses omit intermediate duplicate context payloads.

This update changes no feature formulas, runner work, candle scale/data or ADCN
records, and schedules no feature replay. Only the UI backend needs restarting.
