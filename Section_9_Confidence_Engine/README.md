# Price-point confidence evidence (v2)

`engine.evaluate(close, features, previous=..., candle=...)` evaluates the supplied
price point. It does not accept or inspect a decision label, trade result, later
candle, order, or account position. Both directional scores are calculated from
the same point's inputs. These are uncalibrated evidence scores, not probabilities.

Version 1 conflated trend continuation with reversal quality. Version 2 retains
the continuation breakdown but adds an independent reversal breakdown:

| Reversal family | Cap | Close-time evidence |
| --- | ---: | --- |
| Exhaustion | 25 | RSI extremity and EMA stretch in ATR units |
| Rejection | 25 | wick proportion and close position within the candle |
| Turn confirmation | 25 | DI change, price change and RSI change from the preceding candle |
| Location | 15 | candle interaction with known zones, including inside-zone closes |
| Environment | 10 | ATR relative to baseline |

A direction uses reversal evidence when candle geometry shows a rejection or
strong close away from that edge, and RSI/EMA context supports exhaustion in that
direction. Otherwise it uses continuation evidence. Each direction reports its
selected mode and coverage; the mode is derived from price context, not a BUY or
SELL flag and not whichever score happens to be higher. The Data tab exposes both
breakdowns. Missing observations contribute no points; >=75% weighted coverage is
needed for ready status. No peak receives a forced 80/100 merely because price
later fell. A weak or ambiguous point may still score low despite a good outcome.

Continuation retains caps of trend 20, momentum 25, structure 20, location 25 and
environment 10. Neither mode emits a trading decision. Historical inputs must
come from their own closed candle and preceding closed candle; current HTF and
perpetual observations are not silently joined into a past spot score.

Core owns orchestration in `Section_1_Global_Core.analysis`. Section 8 owns DI
signals; Section 9 owns confidence; Section 10 owns opportunity geometry and
scenario tracking. Both engines use the small public `analysis_packet` numeric
contract. They do not import each other or read/write storage. The former
`presentation` module is only a compatibility delegate to the public coordinator.
No BUY/SELL filtering, alternation, sounds or ADCN rows are changed.

Point calculations use bounded input-keyed caches. Only signal/reference points
and the latest closed point need full display annotations; intermediate candles
can advance scenario tracking without duplicating their full analysis payload.
Stored feature repairs may legitimately change the inputs at a historical point;
future price outcomes cannot. The engine creates no historical feature replay.

The original Section 9 reference remains archived under
`section_9_1_scalp_confidence_engine/`. It is not an active implementation. Its
missing-HTF bonuses, copied fallback weights and unsafe optional arithmetic are
not used. Calibration against unseen outcomes remains separate, unfinished work.
