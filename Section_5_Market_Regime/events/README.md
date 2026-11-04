# Research events v1

This catalogue observes existing features. It is not another indicator, a scheduled
engine or an execution system. No Section 4 formulas, BUY/SELL rules, confidence,
opportunity calculations or runner budgets are changed. No replay is scheduled.

## Sources and vocabulary

| Source | Recorded observation |
|---|---|
| Active structure candidate high/low | STARTED, UPDATED, CLEARED |
| DI+, DI−, signed-spread candidate high/low | STARTED, UPDATED, CLEARED |
| Existing `structure_events` | Confirmed PIVOT_HIGH/PIVOT_LOW, BOS, CHOCH |
| Existing `di_anchor_events` | Confirmed DI high/low, qualification retained |
| Momentum's price-anchor link records | REFERENCE, not duplicate pivot confirmation |

A **candidate** is the existing structure/momentum engine's developing extreme.
A closed candle can update a candidate without confirming a swing. The catalogue
uses `candidate_pivot` to select the active structure side; stale fields for the
inactive side are ignored. A CLEARED candidate means it became inactive/absent;
it does not establish invalidation. It may have confirmed or changed phase.
Candidate changes and confirmations can share a knowledge time. Later strategies
must process that candle's event group together rather than invent an intrabar order.

DI turns retain the existing producer's reversal/spacing rules and independent
`qualified` flag. A confirmed turn can be unqualified. This is not a new detector
for every three-bar wiggle. If added later, a three-bar DI turn needs a separate
name/version so its meaning cannot be confused with the anchored detector.
Thresholds remain the existing Momentum configuration; they are not changed here.

## Causality and identity

Every normalized event has catalogue version, ID, symbol/timeframe, family/stage,
indicator channel, value/units, observation candle, origin (when exported), logical
knowledge time, source-generation reference and original evidence. Original source
IDs, classifications, qualification and price-anchor references are preserved.

A candidate change is observable at the current candle's close. Its underlying
extreme may originate earlier. DI candidate origins are not exported by Section 4,
so they remain **unknown**, never inferred from the observation candle. Confirmed
DI/structure origins and confirmation times come from their original event records.
BOS/CHOCH can lack an origin reference; this remains explicit.

Historical knowledge times are reconstructed closes, **not actual publication logs**.
Historical recalculation could have occurred later. These events cannot establish
that a trade was executable at the extreme's price or at the reconstructed close.
No future candle is read to confirm a past event. Future/invalid event timestamps,
malformed payloads and unready structural lineage are rejected with warnings.

One predecessor candle seeds each historical page. The start of a window does not
fabricate a STARTED event for a candidate already underway. Missing rows or candle
gaps suppress adjacent candidate comparisons; DI comparisons also require continuity.
Native confirmed records are separately admitted using their explicit knowledge time.
Stable normalized IDs include the source generation and catalogue version. Repeated
identical source records are deduplicated; different calculation generations remain
distinguishable.

## Historical viewer

Open **Analysis → Chart analysis → Historical events**. Select a symbol and one of
1m, 5m, 15m, 30m, 1h; start with BTCUSDT 5m. Click Load events. Filter stages, inspect
Evidence and catalogue/source configuration, page older results, or jump to the
observation/confirmation candle. Nothing is fetched until requested; there is no
new poller or chart overlay. Before (UTC) excludes candles not yet closed by that
time. Clearing/changing controls invalidates the displayed window.

Core reads the existing raw/feature stores in read-only transactions. Each request
inspects at most 1000 candles plus one predecessor, bounded by the committed feature
checkpoint. Output is capped at 2000 events using whole-candle groups; older paging
continues without losing part of a candle's events. Required formula/config replay
must be complete. Paused/incomplete 1m history may therefore report unavailable;
this viewer never re-enables a timeframe or computes missing features itself.
The source adapter currently labels Binance USDT **spot** candles, not perpetuals.

API: authenticated `GET /api/events/history?symbol=BTCUSDT&interval=5m&limit=250`;
optional `before` is UTC milliseconds. `GET /api/events/catalog` lists definitions.
An optional development CLI uses the same read-only projection:

```bash
python3 inspect_events.py BTCUSDT --timeframe 5m --bars 250 --summary
python3 inspect_events.py BTCUSDT --timeframe 5m --bars 1000 --output btc_events.json
```

This v1 reads the **current committed feature generation**. It does not create a new
immutable event-history database or preserve old formula generations after source
rows are upgraded. Export the JSON report to freeze a research sample. The report
records source version/config/epoch identity; no trading outcome is claimed.

## Next research step

Build one explicit setup state machine consuming event sequences and anchor
references, with expiry/invalidation. Then join confirmed Trend/Regime public results
using causal availability, followed by execution-cost-aware evaluation on unseen
data. None of those steps changes the active decision engine in this release.
