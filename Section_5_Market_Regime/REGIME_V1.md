# Regime v1 implementation specification

This is the first independent analytical engine, running in research/shadow mode.
It does not replace the existing six-state Section 5 interpretation or change
UI, runner scheduling, decisions, confidence or opportunity. Core owns bounded
input projection, immutable input bundles, storage and checkpoint transactions.

## Frozen experimental configuration

ADX trend entry/hold/range: 25/21/18; ER entry/hold/range: .45/.35/.30;
absolute signed dominance entry/hold: .10/.05. Primary+direction is confirmed
after three consecutive qualifying closed candles. Volatility level and change
have independent three-candle confirmation counters. These are configurable
research assumptions, not calibrated predictive rules.

Directional rules follow contracts/engines/01_regime.md: evaluate trend hold
first, then trend entry, then range entry, otherwise transitional. Within the
entry deadband transitional direction is neutral. Missing required directional
inputs clear only that dimension; they do not carry forward a stale label.

Relative volatility: NATR prior-baseline percentile <10 extremely low, [10,25)
low, [25,75) normal, [75,90) high, >=90 extreme. Require the full configured
prior baseline (default 500), its degeneracy flag and finite nonnegative NATR.
A full valid zero-NATR + zero-movement window is extremely low even if tied rank
is 50. A constant nonzero baseline may rank normal, with a degeneracy quality
flag and half evidence contribution; it is not interpreted as a flat market.

Volatility change uses Section 4's two five-interval fractional changes. Both
>= +.05 propose expanding; both <= −.05 propose contracting; both strictly inside
(−.05,+.05) propose stable; disagreement/ambiguous boundaries propose unknown.
This finalizes the earlier draft gate: BBW *change* corroborates NATR change;
BBW percentile remains independent relative-level context, not direction of
change. Percentile level cannot tell whether volatility is rising or falling.
Zero past denominators remain unavailable. No indicator is recalculated here.

A raw candle gap resets all confirmation state and yields unavailable dimensions
on that candle. Subsequent valid inputs must confirm again. Duplicate/reversed
opens are rejected. State cannot cross identity/config/source-generation keys.
Provisional evaluation uses a copy and returns the unchanged committed state.

## Coverage, strength and confidence

Full input budget is fixed: ADX .20, ER .20, signed dominance .15, DI+ .05,
DI− .05; valid complete NATR-level family .20; joint valid change family .15.
Missing inputs do not cause renormalization. Directional inputs must also have
valid raw OHLC and known times. BBW rank is context, not a second directional vote.

Strength is `100 * mean(min(ADX/50,1), ER, abs(dominance))` when all directional
inputs are valid. It measures directional movement, not classification reliability.
Confidence is the sum of capped evidence-family contributions: primary .65 ×
confirmation progress × agreement (1 for trending/ranging, .5 for transitional);
volatility level .20 × progress (halved for nonzero degenerate baseline); change
.15 × progress. Unknown candidates contribute zero. The numeric contributions,
coverage and per-dimension confirmation counts are published in measurements.
A pending transition's confidence concerns the candidate evidence; it must be
read alongside candidate/confirmed labels and confirmation status. None of these
scores is a win probability, entry recommendation or replacement for Section 9.

## Identity, source lineage and persistence

Core's current candle adapter explicitly identifies Binance spot, quote USDT,
24/7 UTC unadjusted exchange candles. It does not join perpetual liquidity or
claim stock/session support. All configured timeframes use their actual stored
close times. Policy-paused scopes are skipped.

A run is keyed by identity, engine/config/source signature. Source signature
includes the relevant upstream feature projection, generation and raw policy epoch.
The complete feature signature is checked for admission; unrelated formula owners
do not enter the Regime projection fingerprint.
Input bundles retain only OHLC, required numerical inputs, units, validity and
versions. Their content hashes are referenced by results. Bundles, results and
classification state commit atomically. Same-key deterministic divergence is
rejected. Feature/config/source changes create a new run and preserve old runs.
Old numerical values therefore remain reconstructible after wide-feature repair.

Source reads use the existing Core policy guard and a consistent read transaction.
A pending feature repair or mismatched feature signature blocks that pair rather
than mixing old and new measurements. Backfill resumes in bounded pages. Missing
features stop progress; they are not skipped or filled from later candles.

Current historical source publication times are not recorded. Results explicitly
use HISTORICAL_RECONSTRUCTION + AVAILABILITY_RECONSTRUCTED. `as_of` simulates the
candle close using causal inputs; `computed_at`/`available_at` record the actual
calculation time. This is not proof of live availability or profitability.

Run `python3 run_regime.py --help`. The command defaults to active configured
symbols/timeframes and a global 1000-candle budget, divided across pairs in transactions of at most 200. It does not install a daemon,
change runner policy or start another downloader. A future live scheduler/UI
integration remains separate from this first independently inspectable engine.

## Corrected raw data outside normal ingestion

The current stores do not expose a universal revision ID for arbitrary manual
SQL edits to older candles/features. Such edits cannot be auto-detected from a
cursor alone. After an out-of-band correction, recalculate the relevant features
then start a new `--revision correction-YYYY-MM-DD` run. The prior run/input bundles
remain unchanged. This limit is explicit; a content hash is not claimed to detect
all upstream corrections or prove historical publication availability.
