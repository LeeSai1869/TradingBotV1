# Active DI-spread buy decision

The active gate is [`rules/di_spread_recovery.py`](rules/di_spread_recovery.py).
The previous scalp scoring-based implementation remains available for future
strategy composition; it is not invoked by this rule.

On **each of the preceding two closed candles**, require:

- −DI > +DI.
- −DI > DI spread.
- +DI < DI spread.

On the current **closed candle**, require:

- +DI ≥ DI spread (equality qualifies).
- +DI > its immediately preceding value.
- −DI < its immediately preceding value.

All values must be finite, nonnegative and available. The existing momentum
feature owns DI spread: `abs(+DI − −DI)`. No ADX threshold or additional filter
is introduced. No SELL/exit condition is inferred. This is a decision signal;
no exchange-order API is called.

| Closed candle | +DI | −DI | Spread | Result |
|---|---:|---:|---:|---|
| t−2 | 10 | 30 | 20 | Setup |
| t−1 | 11 | 30 | 19 | Setup |
| t | 15 | 27 | 12 | BUY |

The first activation seeds its two-bar memory from the latest committed feature
window and evaluates that window's latest closed bar. It does not replay every
older decision from exchange listing. Subsequent closed feature bars are evaluated
in order. Missing raw candles clear setup memory; provisional features and unclosed
candles cannot trigger a decision. If feature replay is behind current time, the
decision processor also waits for calculated values rather than fabricating DI.

The existing runner invokes `processor.py` after Section 4. It writes the signal
and its bounded restart state to ADCN.db atomically. Other score columns remain
intact; this rule supplies no confidence score. The chart reads `adcn.signal_type`
through the existing combined stream and draws a `B` marker on the trigger candle.
A following candle cannot repeat the signal unless a fresh two-candle setup forms.

Rule version 1 and policy epochs are recorded in the checkpoint. Future changes
to its conditions require a version bump. Earlier stored decisions are historical
records; re-evaluating a whole earlier date range is a separate strategy replay.
