# Shared analytical measurements — v1

Section 4 owns these numerical inputs. They do not classify a market, replace the
existing Section 5 regime, emit decisions or change confidence/opportunity rules.
`features/shared_measurements.py` is an additive post-feature calculation, with
explicit input/output dependencies registered in the existing execution engine.
Existing ATR/DI/EMA/volume MA are consumed; they are not recalculated here.

## Configuration

Section 2 `SHARED_MEASUREMENTS` contains optional overrides of validated defaults:

| Setting | Default | Meaning |
|---|---:|---|
| measurementERLength | 20 | Intervals in efficiency ratio |
| measurementBBLength / measurementBBMultiplier | 20 / 2 | Bollinger population SD window/multiplier |
| measurementRankLength | 500 | Prior contiguous NATR/BBW observations |
| measurementSlopeLength | 5 | EMA slope interval |
| measurementMomentumLength | 10 | ROC/normalized displacement interval |
| measurementReturnLength | 20 | Log-return volatility and directional fractions |
| measurementChangeLength | 5 | NATR/BBW fractional-change interval |
| measurementMACDFast / Slow / Signal | 12 / 26 / 9 | Close EMA/signal periods |

Integer windows must be 2–5000, fast < slow, multiplier in (0,10]. A parameter
snapshot/hash is attached to every result. Changing these settings schedules
replay of the new group only. The current wide store holds one active parameter
configuration; it does not claim simultaneous multi-configuration history.

## Output contract

| Fields | Definition / units |
|---|---|
| di_signed_dominance | (DI+ − DI−)/(DI+ + DI−), signed fraction; valid total zero → 0 |
| directional_movement_zero | True only for a valid zero DI total |
| efficiency_ratio | Absolute net close movement / sum of absolute interval movements; [0,1] |
| zero_price_movement | Entire complete ER window is flat |
| bb_middle, bb_stddev, bb_upper, bb_lower | Close SMA, population SD (ddof=0), SMA ± multiplier × SD; price units |
| bb_width_fraction | (upper − lower)/middle; fraction |
| natr_pct | 100 × existing ATR/close; percent; valid zero ATR stays zero |
| natr_percentile, bb_width_percentile | Midrank [0,100] against full prior contiguous baseline; current value excluded |
| natr_baseline_count, bb_width_baseline_count | Number of valid prior observations before current insertion |
| natr_baseline_degenerate, bb_width_baseline_degenerate | All full-baseline observations equal; unavailable before full baseline |
| natr_change_fraction, bb_width_change_fraction | (current − value k intervals ago)/past value; unavailable for zero past denominator |
| ema50_slope_atr, ema200_slope_atr, ema300_slope_atr | (current EMA − EMA k intervals ago)/current ATR; dimensionless |
| roc_pct | 100 × (close/current-window-start-close − 1); percent |
| momentum_atr | (close − close n intervals ago)/current ATR |
| momentum_atr_change | One-step signed change of momentum_atr |
| momentum_strength_change | One-step change of absolute momentum_atr |
| macd_line, macd_signal, macd_histogram | Fast−slow close EMA, signal EMA, difference; price units |
| realized_volatility | Population SD of log returns; unannualized fraction |
| return_skewness | Population third central moment / SD³; unavailable when SD=0 |
| positive_return_fraction, negative_return_fraction, flat_return_fraction | Counts/n; all valid returns including flats form denominator; sum=1 |
| relative_volume_valid, relative_volume | Valid finite nonnegative volume and strictly positive existing MA; ratio, no invalid-MA zero fallback |
| volume_change_pct | 100 × (current−previous volume)/previous volume; previous must be >0 |
| price_progress_per_relative_volume | Signed one-interval fractional close return / relative volume; volume must be >0; not aggressor flow |
| measurement_contiguous_bars, measurement_gap | Valid positive closes in current run; detected timestamp discontinuity |
| measurement_version, measurement_config_id | shared-v1 and SHA256 of canonical numerical configuration |

A percentile is `100*(count(prior<x)+0.5*count(prior==x))/N`. Exact stored float
comparisons are shared by batch/streaming paths. A constant baseline ranks 50;
use degeneracy/zero flags rather than interpreting that as normal volatility.
Ranks require N prior valid observations: with default BB20, the first BBW rank
is on candle 520. ER20 needs 21 closes. Slopes need k+1 finite EMA samples and
positive ATR. Return statistics need n+1 closes. MACD uses first-close EMA seeds,
alpha=2/(n+1), and remains unavailable until slow+signal−1 contiguous candles.
Other values remain unavailable until their own prerequisites are valid.

## Continuity, storage and boundaries

Input timestamps must strictly increase. The expected next open is the previous
raw candle's close_time+1, including calendar months. A gap resets this group's
bounded histories; invalid/nonpositive close resets them and produces unavailable
numerical results. Invalid rank samples clear that baseline. Invalid volume does
not invalidate otherwise usable price observations. Zero-volume is measured zero;
missing volume is not zero. Legacy indicator seeds/NA conventions are preserved;
this extension does not silently repair their data or change their definitions.

All history/EMA/rank state lives under `sharedMeasurementsState` in the existing
JSON checkpoint. The regular preview clone remains separate. Numeric outputs use
the feature store's existing additive column migration, known dependency sources
and bounded targeted replay. No second downloader, database or worker is added.
Past features are usable by a closed-candle engine only after that candle closes;
there are no external or higher-timeframe joins in this module.

The shared helper is grouped into Momentum, Trend, Volatility and Volume fields
in the feature registry; provenance fields have their own shared-measurements
entry. Source formula files and their legacy units stay unchanged: notably
`atr_percent` remains a fraction and `di_spread` remains absolute.

## What remains outside Section 4

Existing structure/range/sweep/zone events remain their sources of truth. Phase
sequence interpretation belongs in Section 5. Relative benchmark returns,
sentiment/news and derivatives normalization require explicit point-in-time feed
adapters and source identity; missing sources are not fabricated. Observed order
books remain owned by the independent Core liquidity recorder. This completes the
initial reusable candle-measurement foundation, not external data acquisition or
production validation of the future analytical engines.
