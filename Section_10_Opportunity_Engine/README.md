# Six anchored opportunity areas (v5)

`engine.evaluate(close, features, fee_bps=4, slippage_bps=2, zones=(), as_of_ms=None, timeframe='', candle=None)` calculates a complete
map from one price point. It does not take a BUY/SELL decision as a calculation
input. Section 8 owns decisions; Core selects the decision-candle reference;
Section 10 owns area geometry, point outcomes and subsequent crossing tracking. Core supplies the signal candle
high/low for clearance. Pure point diagnostics without a candle use the point
price as both edges.

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

The old two-pass selection could merge unlimited actual overlaps, permit gap
clusters up to 3 ATR, and discard nearby remaining levels with a 2-ATR spacing
rule. Daily ATR made those effects particularly visible. V5 keeps gap merging removed and applies one explicit clearance rule. The
minimum separation is 2 ATR from the decision candle high/low to the first band,
and the same 2 ATR between the far edge of one band and the near edge of the next.
ATR is frozen at the reference candle. A too-close candidate is audited with its
measured and required clearance; it is not shifted, widened or merged to fit.
The nearest candidate that passes becomes the next band. One pass attaches corroboration without expanding
an authoritative source core. A contributor must overlap at least half the
smaller band, and each family may contribute only once. Co-located same-family
alternatives are audited, not counted as extra confluence or duplicate layers.

Actionable cores have an explicit maximum width: min(0.5 reference ATR, 1% of the
anchor). These are conservative display/model policy values, not empirically
calibrated trading thresholds. A broad native zone can be legitimate; its
original bounds are retained in `context_zones`, with `broad_context_only` in the
selection audit. It is not cropped into a fabricated entry band. A source zone
containing the entry is reported separately in `at_entry`, not silently lost or
misrepresented as a forward target. Missing actionable layers remain absent.

Isolated point references get modeled bands with half-width bounded by 0.05 ATR,
0.05% of the anchor, one quarter of the distance to entry, 5% of the level price,
and one quarter of the nearest other point distance. This protects against large
daily ATR, near-zero levels and point-padding bridges. Modeled bands are labeled;
OHLC-inferred liquidity levels are not observed resting orders. No order-book or
future liquidation claim is made.

`contributors` records original source geometry/timeframe, `families` counts
independent families, and `audit` gives selection, duplication, broad-zone,
at-entry and missing-availability reasons. Reports are bounded (256 audit records,
64 broad context records), with truncation/count indicators. The pure result
cache is bounded to 128 distinct inputs. Labels use separate layout with leaders;
price geometry never moves to fit text.

## Reference inventory and timeframe

The reference is the decision candle's chart timeframe. There is no automatic
all-timeframe aggregation: a 1D map uses daily source inputs and daily ATR, and
current HTF overlays cannot be backdated into a historical decision.

Core supplies stored same-timeframe S/R and institutional S/R lifetimes,
order blocks/breakers and qualified FVG births in addition to scalar nearest-zone,
profile, swing, trend, session, Fibonacci and candle-liquidity fields. Section 10
accepts public zone packets; it never imports private storage or feature code.
Core owns the read-only projection and source completeness labels.

The seed reads at most 10,000 preceding candles. Stored reversible SR/OB events
can reconstruct older active zones by undoing a committed checkpoint to just
before the requested page; epochs, replay masking and contiguous raw/event
coverage must agree. Otherwise bounded history is explicitly partial. FVG
lifetimes use stored qualified births and the existing close-through failure
rule; missing fields/candles invalidate continuity rather than retaining stale
zones. The page then advances stored events to each decision, including only
inputs available by that candle close. No formula replay or database write is
performed. Coverage does not claim the inventory includes unavailable history.

Opportunity > Data shows scope, timeframe, coverage and a collapsible source
selection report. `inspect_price_point.py --opportunity-only --level 0.1748`
provides a compact local report against the frozen reference. This can explain
whether a particular source was present, broad, duplicated or outside the first
three; absence of a source in partial history remains unknown.

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

## Durable decision snapshots and marker price

ADCN's `decision_evidence` table now stores one insert-only snapshot for each
canonical BUY/SELL, keyed by symbol, timeframe, candle, data epoch/generation and
side, including the opportunity model version. Older model snapshots are retained;
only the changed evidence map is reconstructed for the new version, without
replaying source features. Its eight primary values are the signal close, directional confidence, three
resistance-band packets and three support-band packets. Each packet retains both
bounds, sources and outcomes. Missing slots are SQL NULL. The full confidence,
opportunity and reference context are retained as JSON with engine versions,
availability time, actual recording time and provenance.

Core's worker bridge coordinates storage after decision commits. Section 8 keeps
its decision rules; Sections 9/10 keep their independent calculations and no
private storage imports. A persistence failure does not undo a decision; bounded
maintenance retries missing snapshots. A separate 64-candle background scan also
fills older chart-projected signals that had no original ADCN row, without
replacing existing decisions or the live decision cursor. Scan progress survives
restarts; missing feature pages remain pending. Historical records are explicitly
labelled reconstructions from stored close-time inputs, never live observations.
No source feature formulas are replayed. Normal chart reads remain read-only.

Historical pages and short reference polls prefer the saved snapshot. Neither
later feature changes nor missing feature rows can move its geometry. A data
reset/generation change isolates the prior snapshot; explicit deletion clears
both evidence and scan records. Current cost settings may reprice the saved
geometry in a read-only copy; they never rewrite the original snapshot or select
new levels. Data identifies this cost preview separately.

Previously the arrow used `aboveBar`/`belowBar`, placing SELL visually at the wick
high while its map used the candle close. Markers now use an explicit price
position and print that same close. Red areas must lie above the labelled signal
reference, green below it, for either signal direction. Wick extrema are not
represented as executable signal prices; the decision is known only at close.

Install by restarting both the runner (for persistence/recovery) and UI backend.
No candle download reset or feature replay is required.
