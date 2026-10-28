# Six anchored opportunity areas (v3)

`engine.evaluate(close, features, fee_bps=4, slippage_bps=2)` calculates a complete
map from one price point. It does not take a BUY/SELL decision as a calculation
input. Section 8 owns decisions; Core selects the decision-candle reference;
Section 10 owns area geometry, point outcomes and subsequent crossing tracking.

## One map, both sides

`areas.resistance` contains up to three red sell/resistance areas above the anchor.
`areas.support` contains up to three green buy/support areas below it. Both arrays
use the same decision-candle price, ATR and feature values. Unknown areas remain
absent rather than filling three slots with invented levels.

After BUY, upper areas represent potential gains and lower areas adverse moves.
After SELL, lower areas represent potential gains/buy-back locations and upper
areas adverse resistance hurdles. All six remain displayed regardless of which
side the decision selected. Each area carries `outcomes.BUY` and `outcomes.SELL`
with cost-adjusted return ranges from that one anchor. The renderer selects and
formats those values; it does not calculate returns from the latest close.

Known directional FVG/OB/breaker inputs cannot enter the wrong side. S/R, profile,
swings, session and individual references take their role relative to the anchor,
so previously broken levels may change role. These are potential barriers, not
predictions that price must turn or executed orders/fills.

## Geometry

Real zones keep their bounds. Actual overlaps merge. The reviewed selection uses
the original distance scales: 1 ATR confluence, 2 ATR layer spacing and 3 ATR
susceptible span. Gap merges are bounded; too-close remaining references can be
retained as enrichment instead of separate congested layers. This restores the
original spatial principles without claiming byte-for-byte legacy fidelity.

Isolated price references get modeled +/-0.1 ATR bands, clipped to their side of
the anchor. They are labeled modeled, not represented as real S/R or observed
order-book liquidity. Sources/families and both edges remain inspectable. Labels
use separate layout with leaders; their price geometry never moves to fit text.
Old numbered source files remain reference material, not active engine imports.

## Frozen calculations and later observations

Core calls confidence/opportunity evaluation on decision/reference candles only.
WAIT candles reuse the frozen snapshot. A new decision replaces the snapshot;
current price, current ATR and newly formed zones cannot move its existing areas.
Input-keyed bounded caches avoid recomputing identical reference inputs on polls.
Explicit public point diagnostics remain available independently.

`context.py` updates tested/crossed/current-location states and `next_area` for
both sides using later closed OHLC only. A resistance crossing requires a close
above its far/high edge, support below its far/low edge. A wick is only a test.
Progress continues after legacy model-risk thresholds or favorable target touches.
Gaps mark coverage unknown while retaining the known reference. OHLC cannot
establish target/stop intrabar order or fill sequence; no profitable fill is inferred.

Two-candle chart polls send `analysis_reference` through the existing combined
request. Core verifies the canonical reference and advances at most 10,000 raw
candles without reading full feature history. Two additional seed candles handle
references at the page's lookback boundary. A short page must never silently
replace the reference with its current close.

## Costs, compatibility and UI

Per-side defaults: fee 4 bps and slippage 2 bps, editable in settings. Costs apply
to entry and exit notionals. Amounts are conditional potential returns, not
expected profit; funding, taxes, leverage, sizing and fill probability are absent.

Legacy `buy.targets` means upper areas and `sell.targets` means lower areas.
Legacy invalidation/risk/reward-risk and single `opposing_band` fields remain
auxiliary compatibility data. They no longer select or hide the chart's six-area
map. The main map shows the anchor reference line, not an extra model-stop area.
A missing modeled stop cannot erase otherwise known areas.

Settings > Features > Opportunity offers six independent area switches, labels,
anchor reference and per-area style controls. Completed/invalidated reference
maps stay visible until the next decision, with crossing information. The old
unanchored-preview chart switch is removed. `inspect_price_point.py` defaults to
anchored outputs; `--include-point-preview` is a separate opt-in diagnostic only.

No feature formulas, candle data, ADCN rows or trading rules are changed. No new
feature columns, historical replay, exchange calls or runner work are introduced.
Only the UI backend needs restarting.
