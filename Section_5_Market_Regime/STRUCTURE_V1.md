# Structure v1 state adapter

This second independent Section 5 engine interprets existing Section 4 outputs.
It does not detect another pivot, change the original structure algorithm or feed
BUY/SELL decisions. Core's shared analytical worker owns its inputs and history.

## Explicit source mapping

`STRUCTURE_BULL` + coherent bullish-active flag maps to BULLISH / HH_HL;
`STRUCTURE_BEAR` + coherent bearish-active flag maps to BEARISH / LH_LL;
`STRUCTURE_RANGE` + coherent range-active flag maps to NEUTRAL / RANGE.
HH_HL/LH_LL name the existing bullish/bearish pattern families, including the
source's equal-high/low tolerance; they do not claim a new strict pivot test.
Unknown enums or conflicting active flags do not become directional evidence.
A supported established state is CONFIRMED; an unestablished state is DEVELOPING.
A newly observed source BOS counter increment reports BROKEN for that candle.
No wick crossing is independently reinterpreted as a confirmed-close break.

Candidate `new_high_type` / `new_low_type` fields are intentionally excluded:
those names describe candidate comparisons, not a confirmed pivot event stream.

## Events and limits

Cumulative bull/bear/range BOS counters provide a conservative event cursor.
The initial seed absorbs existing counts silently. An increment produces a
source-reported BOS; if the source CHOCH enum also changed to a known CHOCH enum,
the reported event is CHOCH. Repeated labels/counts produce no new events.
Counter decreases or raw gaps reset observation rather than invent lost events.

IDs derive from identity, feature source signature, source counter values, event
kind and known candle-close time. They are adapter IDs, not fabricated original
pivot IDs. Source counters do not provide the broken pivot's origin timestamp:
event origin is explicitly null. Repeated same-type CHOCH events without a source
ordinal cannot be reconstructed reliably and are not guessed from a persistent
last-CHOCH string. The source BOS increment remains observable.

A complete confirmed-pivot event adapter is NOT claimed. In particular, we cannot
use nearest-swing reference changes as though they were chronological new pivots.
Confirmed HH/HL/LH/LL events with full original IDs and known times need an explicit
source event export before this adapter can report complete pivot lineage.

## Scores and validity

Fixed coverage budget: .60 coherent established state, .20 valid break counters,
.20 confirmed pivot event lineage. The last family remains unavailable, so maximum
coverage/confidence is .80 and overall quality remains PARTIAL. No renormalization.
Confidence here measures source evidence coverage, not win probability.
Strength=100 means source establishment is complete, not a strong market trend;
otherwise it is unavailable. Missing/future inputs, raw gaps and invalid candles
are handled explicitly. Previews neither commit state nor emit new events.

The same Core history, immutable projections and atomic checkpoints used by
Regime own these results. Storage keys distinguish engine/version/config/source.
No Section 4 formulas, decision policies or UI overlays are modified.
