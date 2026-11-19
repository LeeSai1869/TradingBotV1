# Feature review 01: Trend / EMA gaps and compression

Scope: eight candidate outputs assigned to Trend by the registry. Raw-price fields
have no candidates in the prior scan. Base EMAs remain outside this retirement
proposal: they are displayed by the UI and several feed Section 5 Trend directly.

| Field | Current meaning | Proposed retention |
|---|---|---|
| `ema_gap7_25` | Absolute EMA7 minus EMA25 difference | Derive when consumed; no separate per-candle history |
| `ema_gap25_50` | Absolute EMA25 minus EMA50 difference | Derive when consumed |
| `ema_gap50_100` | Absolute EMA50 minus EMA100 difference | Derive when consumed |
| `ema_gap7_25_pct` | First gap divided by current close | Derive when consumed |
| `ema_gap25_50_pct` | Second gap divided by current close | Derive when consumed |
| `ema_gap50_100_pct` | Third gap divided by current close | Derive when consumed |
| `ema_compression` | Arithmetic mean of the three fractional gaps | Continue calculating for Transition; derive for historical reads |
| `ema300_slope_atr` | EMA300 change over the configured slope lookback, divided by current ATR | Candidate for on-demand calculation after continuity/warmup checks |

The `_pct` values above are fractions in the current implementation. There is no
multiplication by 100. The ATR slope is a total change across the lookback, not a
per-bar average. Preserve these exact semantics.

## Consumers and calculation cost

`Section_5_Market_Regime/features/transition.py` reads `emaCompression` to calculate
`compressionBuilding` and ultimately `transitionState`. Thus the earlier absence
of a snake_case named reference does not mean that the calculation is unused.
It still does not establish a need to retain a separate historical copy.

The seven gap/compression outputs require three absolute differences, three
divisions and an arithmetic mean from retained EMAs and candle close. A local
200,000-iteration arithmetic-only timing measured about 0.097 microseconds per
combined evaluation at its best. That excludes lookups, runtime NA handling,
serialization and I/O; it is not an end-to-end engine benchmark.

The eighth output is exported by `shared_measurements.py`. Its default lookback
is five bars. Reconstruct it from retained EMA300 history and current ATR without
replaying the recursive EMA itself, but preserve the measurement state's reset,
missing-value and warmup rules. No present downstream named consumer was found
by the preliminary scan; configurable research remains a possible consumer.

## Migration requirements before retirement

1. Keep existing live calculations and checkpoint state.
2. Adapt selective replay hydration so gaps/compression can be supplied from their
   retained inputs instead of requiring physical historical columns.
3. Resolve configurable alert/export/research requests through a derived-field
   provider, preserving nulls and historical formula versions.
4. Verify old stored values against reconstructed values, including zero/missing
   denominators, discontinuities and historical parameter changes.
5. Measure actual storage contribution before estimating physical disk savings.

Decision proposed for review: retire permanent storage of the seven cheap
same-candle derivatives after those adapters and parity checks. Treat the ATR
slope separately until lookback/continuity parity is demonstrated. No production
fields were removed as part of this review.

Sources: `features/trend.py`, `features/shared_measurements.py`,
`Section_5_Market_Regime/features/transition.py`, the feature registry and the
selective replay implementation.
