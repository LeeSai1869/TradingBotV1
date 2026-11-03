# Sentiment v1.0.0 — partial derivatives context

V1 describes **indicative funding tilt**, changes in funding/open interest and
reported liquidation stress from the existing Binance USDT perpetual recorder.
It does not claim broad crowd/news/social sentiment, hidden positioning, forecast
liquidation maps or a trading edge. Funding is one positioning proxy, not measured
market optimism. Every result declares scope DERIVATIVES_FUNDING_TILT_ONLY.

## Boundaries and execution

Section 5 is pure interpretation: no SQL, network fetches, other engine implementation
imports, rolling indicators or feature duplication. Core projects two bounded recorder
rows (current and a five-minute earlier point) plus the latest timestamped symbol or
wildcard gap using one read-only snapshot per batch. It stores minimal immutable
source bundles/results/checkpoints in intelligence.db. Missing/corrupt optional
storage does not block history or create a recorder database. A corrupt older
baseline cannot erase a valid current funding observation.

No new source provider, credential, dependency, news scraper, Section 4 formula,
liquidity-recorder behavior, UI or trading rule is introduced. The existing bounded
runner includes SENTIMENT per active coin/timeframe with its fixed recent 32-candle
seed and subsequent closes. Optional research uses `run_regime.py --engine SENTIMENT`.
Each result is independent of other engines. History survives recorder pruning and
replays exactly from committed source bundles. Revised source generations/operator
revisions create separate runs; old results are preserved.

## Identity and availability

Only explicitly observed, exact-instrument Binance USDT perpetual samples published
by candle as_of are admitted. Publication/sample age must be <=10 seconds; future
publication or a later gap is rejected. Funding/mark/index receipt and exchange times
must also be <=10 seconds old and not in the future. OI has a separate <=120-second
context bound. Source gaps invalidate affected historical windows.

Spot charts require an explicit RELATED_PERPETUAL_CONTEXT association with a fresh
perpetual mid and the closed spot price/time. Recompute/check basis (default maximum
absolute basis 100 bps), book timestamps and synchronization sequence. Outputs retain
perpetual source identity plus PERPETUAL_POSITIONING_CONTEXT_NOT_SPOT_SENTIMENT.
An exact perpetual identity can use EXACT_MARKET; mismatched assets/venues and other
associations are rejected. This is related-market evidence, not spot sentiment.

The earlier row must have been published at/before as_of minus five minutes and be
fresh at that boundary. Funding delta requires 280–320 seconds between actual mark
measurements. OI change requires a positive earlier OI, actual interval 180–420 seconds
and no intervening gap. Both actual windows are exposed, not silently rounded.

## Independent classifications and configurable research defaults

- `sentiment`: BULLISH for indicative funding >=+.00005, BEARISH <=-.00005, otherwise
  NEUTRAL. A genuine observed zero can be neutral; missing funding is UNKNOWN.
  These labels mean **funding tilt only**. Rates are raw fractions for the provider's
  quoted funding period, not annualized, settled or normalized to eight hours.
- `stability`: current minus earlier raw funding. Absolute change >=.00020 is
  RAPIDLY_CHANGING; >=+.00005 IMPROVING; <=-.00005 DETERIORATING; otherwise STABLE.
  Improving means more positive funding tilt, not safer or more profitable conditions.
  It is a five-minute point comparison, not bar-by-bar momentum or a broad mood trend.
  A funding-period change may also change raw quoted rates; comparisons do not
  claim normalized economic equivalence across periods/instruments.
- `positioning`: always UNKNOWN in this version. Positive/negative funding alone
  cannot establish LONG_CROWDED/SHORT_CROWDED, nor can zero funding establish BALANCED.
  Historical normalization and proper positioning/account-ratio sources are absent.
  EXTREMELY_BULLISH/EXTREMELY_BEARISH likewise remain unavailable.
- `risk`: EXTREME for reported liquidation rate >=2,000,000 USDT/second, HIGH for
  >=200,000, calculated only from an explicit, gap-free sampled recorder window
  <=10 seconds. This is a reported lower-bound stress heuristic, not a complete
  market liquidation rate or whole-candle aggregate. Without that stress evidence,
  OI growth >=1% combined with absolute funding >=.00030 yields MODERATE as a leverage
  buildup heuristic. Otherwise UNKNOWN. Zero sampled liquidations never proves LOW.

Current zero OI is a valid observation; zero baseline is not divided by. OI changes
remain measurements, not an inference about which side opened positions. No account
ratio or price-only proxy is relabeled as traders' contract notional or sentiment.
These thresholds are experimental, particularly absolute sampled stress thresholds
across assets. They are not calibrated strategy weights or probability estimates.

## Missingness, history and scores

Dimensions remain independent: valid reported stress can coexist with missing funding;
a bullish funding tilt can coexist with HIGH risk. No source returns all UNKNOWN,
not NEUTRAL. Candle gaps are flagged separately from still-fresh external context.
Provisional requests return prior confirmed classification, UNKNOWN candidates,
no new events and unchanged state. Confirmed classification changes emit stable-ID
SENTIMENT_TRANSITION events at current knowledge time, never backdated source times.
Repeated unchanged labels do not duplicate events.

Fixed evidence budget:

| Family | Weight |
|---|---:|
| Fresh indicative funding | .15 |
| Valid earlier funding comparison | .05 |
| OI change with valid earlier point | .10 |
| Explicit reported liquidation window | .10 |
| Historical normalized positioning (unavailable) | .10 |
| Properly scoped account ratios (unavailable) | .10 |
| News sources (unavailable) | .20 |
| Crowd/social sources (unavailable) | .20 |

Missing sources are never renormalized. V1 maximum coverage/confidence is .40 and
quality remains PARTIAL. Confidence is admitted evidence coverage, not probability,
reliability calibration or a claim that one venue represents the entire market.
Strength is nullable without funding; otherwise 100*min(abs(funding)/.00030,1), an
absolute raw funding-tilt intensity score, not crowding or predictive strength.

Diagnostics report every classification dimension, transition counts, quality and
classification changes. Future source adapters must admit publication/revision times,
units, coverage, licenses and same-source historical normalization explicitly before
broad sentiment/extreme/crowding labels can be enabled. Current live data is never
joined onto an unrecorded historical candle. Predictive usefulness requires separate
real-market diagnostics and held-out evaluation.
