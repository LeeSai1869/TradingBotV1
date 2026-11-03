# Shared feature audit and gap register

Audit baseline: repository `c21592d`. This is an inventory of code/contract fields,
not proof that every local symbol has completed replay or that an external feed
is currently healthy. Existing fields are reused only after validity/version and
continuity checks. No measurements are added by this design release.

## Existing measurements and semantic traps

| Existing owner / field | Current meaning | Contract action |
|---|---|---|
| Section 4 `adx`, `di_plus`, `di_minus` | Existing Wilder-derived directional measurements | Reuse; no new ADX/DI calculators in Section 5 |
| `di_direction`, `di_signed_spread` | Signed DI+ minus DI− | Reuse signed evidence; preserve old field identities |
| `di_spread` | Absolute DI difference | Do not treat as signed spread |
| `di_dominance` | Absolute DI difference divided by DI total | Not the proposed signed normalized dominance; add a separately named shared output |
| `atr`, `atr_ma`, `atr_ma_ratio`, `atr_change` | Existing absolute ATR and baseline/change | Reuse existing validity and seeds |
| `atr_percent` | ATR / close, a **fraction**, despite the field name | Logical NATR percent = 100 × this fraction; do not silently change existing units |
| `ema7/25/50/100/200/300` | Existing EMAs | Reuse |
| `ema50/200/300_slope_pct` | One-bar percentage EMA change | Not a multi-bar ATR-normalized slope |
| `candle_efficiency` | Absolute single-candle body / candle range | Not multi-bar Kaufman Efficiency Ratio |
| `volume`, `volume_ma`, `volume_ratio` | Existing volume and current-inclusive average ratio | Reuse only with explicit units/valid MA; legacy invalid-MA fallback ratio 0 is not a valid low-volume observation |
| `candle_range`, body/wicks, change/displacement fields | Existing candle anatomy and movement | Verify units per field; reuse exact semantics |
| Confirmed structure, swing, BOS/CHOCH and zone fields/events | Existing Section 4 state and event sources | Structure engine interprets/adapts, never redetects pivots |
| Momentum DI anchors | Six extrema, known times, price/regime linkage, bounded history | Reuse; no second anchor tracker |
| Core liquidity book/analytics packets | Observed depth, flow, spread/slippage, OI/funding freshness and sampled liquidations | Reuse existing independent recorder, identity and coverage; live recording is not historical coverage |
| Current Section 5 six-state outputs | Existing legacy-compatible regime interpretation | Keep current consumers intact; new multidimensional results need explicit adapters |

## Gap groups referenced by registry.json

| Gap ID | Shared measurement work | Initial consumers |
|---|---|---|
| REGIME_REQUIRED_FEATURES | Signed normalized DI dominance; ER; NATR distribution; BBW/change dependencies below | Regime |
| BOLLINGER | SMA middle, population SD, upper/lower, width fraction; point-in-time validity | Regime, Volatility |
| NORMALIZED_VOLATILITY_DISTRIBUTIONS | NATR percent, past-only NATR and BBW ranks, valid baseline counts and degeneracy flags | Regime, Volatility |
| EMA_NORMALIZED_SLOPES | `(EMA_t - EMA_t-k) / ATR_t`, explicit k and normalization validity | Trend |
| DIRECTIONAL_CONSISTENCY | Fraction of valid signed returns agreeing with the candidate direction; defined neutral treatment | Trend |
| ROC_AND_NORMALIZED_MOMENTUM | ROC(n) percent, `(close_t-close_t-n)/ATR_t`, change in signed and absolute normalized movement | Momentum |
| MACD_OPTIONAL | Shared fast/slow/signal EMA-derived values and histogram if required after evaluation | Momentum; not a Regime dependency |
| REALIZED_VOLATILITY | Unannualized SD of log returns, explicit n; optional separately named skewness/change | Volatility |
| VOLUME_VALIDITY_AND_CHANGE | Validity/units around existing RVOL, volume change and normalized price-progress features | Participation |
| RANGE_SEQUENCE_MEASUREMENTS | Range duration/boundaries and explicit failed-breakout event references, where existing features do not already suffice | Phase |
| RELATIVE_STRENGTH_OPTIONAL | Point-in-time benchmark-relative returns; matched timestamps and benchmark identity | Phase, future context |
| OBSERVED_CANDLE_SUMMARIES_IF_MISSING | Audit existing liquidity summaries before adding closed-candle aggregates for compatible markets | Liquidity, Participation |
| CROSS_MARKET_BASIS_OPTIONAL | Explicit spot/perpetual mark/index/basis association; never a silent cross-market join | Liquidity |
| EXTERNAL_SOURCE_ADAPTERS | Licensed/source-identified news/crowd/positioning inputs only when actually available | Sentiment |
| EXTERNAL_NORMALIZATION | Same-source historical funding/positioning/sentiment baselines and publication/revision metadata | Sentiment |

These are logical feature families, not instructions to add every proposed column.
Before implementation, map to the current manifest and feature contract again;
reuse any equivalent field with verified semantics. Add only a real missing
measurement. Each feature specification must declare owner, units, inputs,
parameters, warmup, gap/zero handling, availability and dependency fingerprint.

## Initial numerical conventions for the Regime feature work

- Signed dominance: `(di_plus-di_minus)/(di_plus+di_minus)`, range [-1,1]. A valid
  zero DI total gives 0 plus DIRECTIONAL_MOVEMENT_ZERO; missing DI remains missing.
- ER(n=20): absolute net close change over n intervals divided by the sum of n
  absolute close changes. It needs n+1 valid contiguous closes. A genuinely flat
  complete window gives 0; incomplete history is unavailable.
- Bollinger(n=20,k=2): SMA(close), population SD (ddof=0), middle ±k×SD.
  Width is `(upper-lower)/middle`, a fraction, not percent. A nonpositive/invalid
  middle makes width unavailable. Its width-percent output, if needed, has a
  different explicit name/units.
- NATR: `100*ATR/close`, percent. A nonpositive/invalid close is invalid. Zero ATR
  from a valid flat series is a measured zero, not missing data.
- Percentile(current x; N=500 **prior** valid contiguous values):
  `100*(count(v<x)+0.5*count(v==x))/N`. Current x is excluded from the baseline;
  comparisons use the same numerical/rounding policy in batch and streaming.
  Require the full configured baseline initially; never silently rank against a
  few warmup rows. Publish baseline count and DEGENERATE_BASELINE for all ties.
- A constant nonzero distribution has middle rank 50 under this convention. True
  zero movement is separately flagged and may classify EXTREMELY_LOW; rank 50
  alone must not label a flat market as normal absolute movement.
- Return volatility: unannualized population SD of n valid log returns. No 252-day
  or 365-day annualization is silently applied across markets/timeframes.

Store/configure logical feature IDs plus parameter hashes rather than proliferating
columns for every n/k combination. Preserve existing wide-store contracts until
an explicit migration defines how multiple configurations coexist.
