# Six anchored opportunity areas (v6)

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

## Geometry: native-source hierarchy

Geometry follows the local priority S/R (including institutional), FVG, OB, then
breaker. An existing higher-priority native zone keeps its **entire original
bounds**; there is no 0.5-ATR/1%-of-price width cap. The narrowest source no longer
wins just because it is thin. Priorities apply to the same overlapping region:
a distant S/R does not displace an unrelated nearer FVG.

A point inside a native zone corroborates it. Another zone corroborates it if
at least half the narrower zone overlaps. Adding evidence never expands, shrinks
or unions native geometry, so overlap chains cannot create a giant envelope.
All stored EMA periods, WMA50 and VWAP/band references participate as correlated
trend evidence, counted as one family. Every attached source is retained in
`evidence`/`sources`; `contributors` contains
one representative per family and the family score counts distinct families once.
`geometry_source` identifies which actual source supplies the boundaries. Another
same-family source may add provenance, never a second independent family score.

Where no native core exists, fallback modeling requires **at least three distinct
feature families** within a maximum 1-ATR source envelope. A cluster becomes a
1-ATR-wide band centered on that envelope, retaining all member levels inside.
No chain can exceed the confluence threshold; one EMA, one VP level, or three
correlated trend lines cannot independently create an OZ. Modeled padding cannot
overlap a native core and override its priority. Non-primary profile intervals
that exceed the confluence width remain context, not fabricated point levels.
These are modeled reaction regions, not observed resting orders or calibrated
probabilities.

Both native and modeled zones obey the existing **2-ATR clearance** from the
decision candle's full high/low to band 1, and the same edge-to-edge clearance
between later bands. ATR is frozen at the decision candle. A native zone that
fails clearance is reported with its full bounds and reason; a thin FVG inside
it cannot bypass that check. The engine chooses the nearest three qualifying
regions per side. It does not label every visible chart zone or invent six slots.

`audit` records source/geometry priority, confluence, clearance and availability
reasons, bounded to 256 records with count/truncation indicators; context records
are bounded to 64. The input cache remains bounded to 128 snapshots. Data shows
the source that supplies each area's geometry. Chart label layout does not move
price boundaries. New v6 ADCN snapshots are isolated by the existing model-version
key: old maps remain archived; only Opportunity evidence is rebuilt. Source
feature formulas, decision rules and historical candle/feature memory are not
recalculated or replaced.

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

Compact arrow flags sit above/below the signal candle, showing BUY/SELL and
confidence on two lines. The saved signal close remains the reference for all
return calculations; flag position is presentation only. Zone clearance is
measured from the full candle high/low, with red above and green below. Wick
extrema are not represented as executable signal prices; the decision is known
only at close.

Install by restarting both the runner (for persistence/recovery) and UI backend.
No candle download reset or feature replay is required.

## Compact chart presentation

OZ rectangles span the decision candle through the current candle only, including
the forming candle when available. They do not extend across the empty future
margin or attach to the price axis. Price bounds, the shared 2-ATR separation,
anchors, scores and stored ADCN records are unchanged by this UI update.

Labels use `OZ1`, `OZ2`, `OZ3`; red/green preserve resistance/support roles.
The optional `2F` score is the existing number of distinct contributing feature
families, not a calibrated percentage strength or win probability. Unknown scores
show a dash. Select/Deselect All Scores and six per-area score switches are in
Opportunity > Display. Return percentages have a separate switch and are hidden
by default. Full geometry, outcomes, provenance and source audit remain in Data.

A one-time compact-style preference upgrade hides the decision-price reference
line. Display can re-enable it, now with a short `REF` label. Existing area
visibility, bounds, costs, colors and explicit score preferences are retained.
BUY/SELL flags use two lines (`BUY` / `88%`) and arrows, without mode, price or
explanation strings; the percentage represents the stored evidence score /100.
S/R, FVG, OB, liquidity and VP annotations also use abbreviations. Liquidity's full
health explanation remains in the badge tooltip and its Data tab.

Only restart the UI backend and hard-refresh. No runner restart, recalculation or
memory migration is needed for these display changes.
