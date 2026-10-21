# TradingView reference review

Reference: `sections_4&5_Tradingview`, Git commit `e940218`.
Previous Python engine: `backups/pre_tradingview_e940218.zip`.
The backup contains source only, not databases or credentials.

## Implemented and connected

| Reference | Python owner | Status |
|---|---|---|
| 4.2.1 Price | `features/price.py` | Current/previous OHLC and compatible price aliases |
| 4.2.2 Trend | `features/trend.py` | EMA family, gaps, compression |
| 4.2.3 EMA structure | `features/ema_structure.py` | Structure, distances, slopes, nearest EMAs |
| 4.2.5 Price location | `features/price_location.py` | EMA-relative flags; VWAP-relative flags remain owned by VWAP |
| 4.2.6 Momentum | `features/rsi.py`, `features/di_adx.py` | SMA-seeded Wilder RMA; previous values; DI signs; five-bar RSI divergence |
| 4.2.7 Volatility | `features/atr.py` | SMA-seeded Wilder ATR, average, ratios and change |
| 4.2.8 Volume | `features/volume.py` | Existing volume/SMA/ratio calculations retained |
| 4.2.12–13 Candle/change | `features/candle.py` | Corrected upper-wick ratio, signed body, neutral close location, fractional change; added displacement/pattern fields |
| 4.2.4 VWAP | `features/vwap.py` | Corrected signed distance and reference band type names; see limitations below |
| 4.2.18 Profile | `features/volume_profile.py` | Extracted from mixed location file; prior bounded-expansion fix retained |

`feature_builder.py` resolves the registry in dependency order. `ema.py` is now
a compatibility facade for existing live calculations, not a second formula
implementation. The unused combined `market_context.py` is archived and removed.
Support/resistance, BOS, imbalance and liquidity retain their existing modules.
They have **not** been replaced or certified equivalent to this reference.

Pure output fields are now added to permanent storage instead of being silently
discarded by its previous restricted column list. Schema migration preserves
existing rows. Newly calculated rows carry `formula_version=2`; existing rows
are labelled version 1. Existing rows are **not automatically recalculated**.
Do not compare old and new formula histories as though they were homogeneous.
No candle data is deleted by this update.

## Limits requiring further translation/validation

This is not a complete 5,900-line Pine port or a claim of numerical parity for
the whole engine. The reference is a fragment, not a standalone executable:
it depends on Section 3 `MTFData`, global inputs and `marketMemory`. It also
declares `prevBodyPercent` twice in the same function. Defaults for external
parameters cannot be verified from this fragment; existing Python lengths are
retained (RSI 7, ADX 10, ATR 10/14, configured EMA lengths).

Python currently recomputes recursive indicators on a rolling 500-bar window.
Even with correct smoothing and seeding within that window, this is not identical
to Pine's uninterrupted full-history recurrence. Session VWAP can omit the first
part of a UTC day on short intervals when it lies outside that window. The Pine
VWAP band code mixes `mtfData.vwapValue` with chart-context `hlc3`/`volume`, which
requires an explicit MTF/session interpretation before claiming cross-timeframe
equivalence.

The newer dynamic/institutional S/R lifecycle, full Fibonacci/swing/location,
FVG/order-block rules and regime-memory replay still require a separate audited
translation and restart/replay strategy. Existing runtime state uses additional
Python contracts; replacing those files wholesale without replay would not be
a faithful migration. A complete historical recalculation should be done only
after that migration is implemented, against a backed-up feature database.

`tests/test_pine_features.py` verifies hand-calculated RMA/RSI/ATR/DMI vectors,
candle units, split EMA compatibility, signed VWAP distance and non-destructive
schema migration. It is not a TradingView export comparison.
