# Candle liquidity proxy review

This numbered feature module infers liquidity from candles. It is distinct from
`Section_1_Global_Core/liquidity/`, which observes actual perpetual orders/trades.
No correction here turns candle inference into an observed depth or liquidation map.

Reviewed corrections, mirrored in Pine and regenerated Python:

- `internalLowDistancePct` names the percentage explicitly. Exported legacy
  `internal_low_distance` remains percentage-valued for contract compatibility;
  no duplicate stored percentage column is introduced.
- Low importance checks the percentage it consumes, not absolute distance.
- `liquiditySide` compares the two percentage distances. A range containing the
  current candle cannot normally put its close outside that range, so the old
  comparison was effectively constant. Ties retain MID_RANGE; unknown is UNKNOWN.
- Sweep strength and ATR distances explicitly require positive, known ATR.
  Known price distances remain available even when ATR has not warmed up.
- Reclaim/rejection and strength use the already computed prior window extremes,
  avoiding a redundant shifted lookup of the same rolling level.

Other findings:

- `liquidityLookback` already comes from Inputs and is validated by Context.
- Runtime division by zero returns NA, not ZeroDivisionError. Explicit guards
  improve intent and avoid treating negative ATR as valid; no infinity is needed.
- Cluster/age loops already have verified execution kernels; age scanning stops
  after both matches. `barssince` against a *changing* external extreme is not
  equivalent to rescanning prior highs against today's extreme. No substitution.
- Existing 10/20/5-bps proximity thresholds are retained. ATR-relative variants
  would be new model features requiring distribution and outcome validation.
- Importance remains 0–10, absorption 0–100. A model can scale these at its input
  boundary; duplicating them in memory is unnecessary.
- Exact zero distance is valid AT_PRICE information. Flooring it to epsilon
  would fabricate distance. Consumers may derive an AT_PRICE category explicitly.
- Exported distance fields are public contract inputs, not proven dead merely
  because this module doesn't consume them. They are not removed speculatively.
- Liquidity type/location/side are nominal categories, not ordered magnitudes.
  Use a declared one-hot/category vocabulary, including unknown handling; never
  silently encode their lexical order as a meaningful numeric rank.

Selective replay fingerprints dirty only this module's affected exports and
actual downstream dependencies. EMA, ADX, S/R, FVG, OB and profile formulas are
unchanged. A 700-bar differential against df2daca changed only liquidity-side
classification and warmup price distances; unrelated output values matched.

Remaining observed-liquidity work is not declared complete: additional venues,
market-matched spot/perpetual comparisons and out-of-sample predictive validation
still need implementation/verification. Existing recording includes source health,
sampled persistence, rolling flow, basis and OI change. A price-point evaluation
cannot use current book/OI to explain an old candle without recorded as-of data.
