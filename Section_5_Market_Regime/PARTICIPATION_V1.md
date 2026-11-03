# Participation v1.0.0

Independent closed-candle classification, not a trading signal. Consumes Section 4
shared measurements through Core. No network, SQL or other engine implementation
imports. Core owns immutable snapshots, version/config-bound history and restart
state in intelligence.db. The normal bounded analytical maintenance includes this
engine for every active coin/timeframe, using the existing saved recent seed.
Historical backfill is separately available through run_regime.py --engine PARTICIPATION.

## Rules and configurable defaults

- Activity RVOL bands: below .5 VERY_LOW, .5–.8 LOW, .8–1.5 NORMAL,
  1.5–3 HIGH, at least 3 EXTREME. Boundaries belong to the upper band.
- Participation change uses the existing one-bar volume percentage change:
  at least +10% INCREASING, at most -10% DECLINING, otherwise STABLE.
  This describes a one-bar comparison, not a sustained volume trend.
- Shared signed price-progress-per-RVOL multiplied by RVOL recovers the existing
  close-to-close return. At least .1% absolute movement with RVOL >=1.5 is
  CONFIRMING; movement with RVOL <.8 is DIVERGING; otherwise NEUTRAL.
  This is price/volume confirmation, not oscillator divergence or a direction vote.
- High volume with little progress adds POTENTIAL_ABSORPTION_OR_TWO_SIDED_ACTIVITY;
  it never asserts actual absorption or trader intent.
- Dominance is UNKNOWN. No matched historical aggressor stream is admitted in v1;
  current perpetual flow is never pasted onto old spot candles.
- All three available dimensions confirm independently after 3 closed candles.
  Gaps reset confirmation. Preview never commits state or events.
- Transition events are emitted only once per confirmed change with stable IDs,
  origin candle time and closed-candle known time.

The required relative_volume_valid flag prevents legacy warmup volume_ratio=0 from
being treated as genuine inactivity. A real zero volume candle with a valid positive
baseline is VERY_LOW; price-progress-per-RVOL remains unavailable at zero volume.
Missing data never becomes zero. Source units, availability, identity, chronology,
finite measurements and the supported 24/7 UTC calendar are checked.

## Scores and coverage

Fixed evidence budgets: activity .35, participation change .20, confirmation .20,
aggressor dominance .25. Missing budgets are never renormalized. Therefore this
candle-only v1 reaches at most .75 coverage and reports PARTIAL, deliberately.
Confidence is the available evidence budget times confirmation progress, not a win
probability or predictive reliability estimate. Strength = 100*min(RVOL/3,1), an
activity intensity score. These thresholds are research defaults, not calibrated
profitability claims. Config changes create separate version-bound history runs.

The existing shared volume MA includes the current candle; this engine preserves
that definition and does not create a competing average or change Section 4.
