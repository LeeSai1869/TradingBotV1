# Directional confidence evidence

Production entry point: `engine.evaluate(close, features)`. The original
`section_9_1_scalp_confidence_engine/Scalp_Confidence.py` remains a reference;
its legacy absolute packet imports are not used by the runtime.

Review of the original found missing HTF inputs awarded confidence, fallback
weights copied from 30m into other frames, unguarded optional arithmetic
(including `abs(directional_displacement)` before its null check), and mixed
uncapped correlated contributions before final clipping. The supplied
`sections_4&5_Tradingview` file contains the feature/regime source rather than
Sections 9/10. This upgrade uses the existing Section 9/10 Python references.

Version 1 produces independent BUY and SELL evidence scores /100. These are
not probabilities, need not sum to 100, and do not estimate win rates. Components:

| Group | Cap | Evidence |
| --- | ---: | --- |
| Trend | 20 | close relative to EMA50, EMA200 and VWAP, scaled by ATR |
| Momentum | 25 | DI direction attenuated by ADX; RSI directional strength |
| Structure | 20 | established bullish, bearish or range classification |
| Location | 25 | nearest available barriers on either side, capped across correlated zone families |
| Environment | 10 | ATR relative to its baseline; nondirectional suitability |

Missing inputs contribute zero points and reduce evidence coverage. Missing
trend/momentum subcomponents reduce their group coverage proportionately.
A score is ready only with positive close/ATR and at least 75% weighted coverage.
Directional preference additionally requires a >=10-point margin. Those are
versioned heuristic thresholds, not calibrated trading recommendations. Adverse
location reduces the favorable-side allocation rather than counting overlapping
S/R, FVG and OBs as independent confirmations. Session bonuses are omitted rather
than asserting that a trading session by itself improves trade quality.

`presentation.annotate` attaches confidence to ready formula-v3 closed bars and
opportunity scenarios to signal bars plus the latest closed row in the page.
It does not change DI signals, ADCN rows, alternation, sounds, feature formulas,
or replay checkpoints. Pure calculations use bounded 8192-entry LRU caches keyed
by their actual inputs; changed repaired inputs invalidate the cached result
without touching unrelated stored feature rows. There are no exchange calls,
DB migrations, historical replay jobs or new runner work. Annotations are
read-only derived views, not additional stored feature copies.

Historical evidence uses only that candle's stored feature row. No current HTF
snapshot, current liquidity book or later candle is joined into a past score.
Version 1 explicitly reports chart-timeframe scope. HTF/liquidity integration
requires market-matched, availability-time joins and is not silently inferred.
Out-of-sample calibration with fees, label horizons and regime splits is required
before interpreting these scores as probabilities or using them to gate orders.

Settings > Features > Confidence offers separate BUY/SELL Display switches and
a Data breakdown. Enabled scores appear beside the corresponding DI marker and
in the latest evidence readout. Insufficient coverage displays confidence pending.
