# Structure 1.1 — confirmed producer event lineage

Structure remains an interpreter of Section 4's existing algorithm. It does not
redetect pivots, change their confirmation conditions or feed BUY/SELL decisions.

## Original source confirmation, exported at the branch

Section 4 now captures PIVOT_HIGH/PIVOT_LOW directly where the existing algorithm
appends a confirmed pivot to its arrays, before the candidate is reset. BOS and
CHOCH are captured where their existing source events are appended, before the
structure arrays are cleared. No new confirmation or break condition is added.

Three additive stored fields expose this channel: `structure_events` (JSON array
for this candle only), `structure_events_version` and `structure_event_status`.
An empty array under a ready protocol means no new events, not missing coverage.

Each event has a deterministic **producer-assigned** ID, original source bar and
origin timestamp, confirming candle timestamp, and earliest closed-candle known
time (`close_time+1`). Pivot events retain price, previous same-kind pivot ID and
strict HH/LH/EH or HL/LL/EL comparison against the previous confirmed same-kind
price. First known pivots have no comparative classification. Candidate geometry
and legacy tolerance-based candidate type fields remain unchanged and unused by
this event channel. Source bar indices are not replaced by viewport indices.

BOS/CHOCH reference the original source candidate bar/type and its confirmed pivot
ID/time when found in the bounded last-64 producer reference cache. If the source
reference is unavailable, origin time/pivot ID remain null and the result reports
BREAK_ORIGIN_UNAVAILABLE. No timestamp or broken level is invented. BOS and CHOCH
are source-reported structural events, not an independently inferred wick/close
crossing rule. Both are preserved when confirmed on the same candle.

Historical known time is the formula's causal availability convention, not proof
of actual historical publication. Core still records reconstruction provenance
and real computation/availability times in its versioned analytical history.

## State interpretation and coverage

The existing source mapping is retained:

- STRUCTURE_BULL + coherent active flag → BULLISH / HH_HL.
- STRUCTURE_BEAR + coherent active flag → BEARISH / LH_LL.
- STRUCTURE_RANGE + coherent active flag → NEUTRAL / RANGE.

These are canonical pattern families, including the source's equality tolerance,
not newly imposed strict-pivot tests. Incoherent flags/unknown enums do not become
directional evidence. A newly emitted BOS/CHOCH makes condition BROKEN for that
candle. Pivot confirmations alone do not mark the structure broken.

Structure consumes producer IDs and classifications directly. Seen IDs are bounded
to 256 per engine/pair. Repeated source labels or cumulative counter changes can
no longer manufacture a new event. Future/mistimed/malformed event batches are
rejected. Previews neither advance committed state nor emit confirmed events.

Fixed coverage budget: .60 coherent established source state, .20 valid diagnostic
break counters, .20 valid confirmed-event lineage. Complete supported input can
now reach 1.0 / VALID. Missing lineage or break origin reduces coverage explicitly.
Confidence measures source evidence coverage, not win probability. Strength=100
means source establishment is complete, not that a market trend is strong.

## Upgrade and boundaries

The normal runner still owns bounded automatic work. Core retains projected inputs,
results and atomic checkpoints in the existing analytical store. Structure engine
and state version advance to 1.1.0; the common envelope stays 1.0.0. Earlier 1.0
runs remain archived. The new source export uses the existing feature-column
migration and dependency-directed replay; capture must replay original structure
confirmation branches, so related structure outputs are recomputed as well.

Legacy calculations are preserved: the existing 700-candle packet regression hash
is unchanged after excluding these three additive fields. Source state is bounded
and included in the existing feature checkpoint. No new downloader, worker, UI
change, decision policy, confidence formula or opportunity geometry is introduced.
