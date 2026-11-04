# Bias v1.0.0 — per-timeframe analytical synthesis

Bias combines versioned public analytical outputs for **one symbol/timeframe and
one closed candle**. It is not a BUY/SELL signal, execution rule, probability or
replacement for Section 9 confidence or Section 10 opportunity. Strong bullish
preference can coexist with extreme risk. The weights below are experimental,
requiring held-out evaluation before strategy use.

## Dependencies, boundaries and history

Read REGIME, TREND, STRUCTURE, MOMENTUM, VOLATILITY, PHASE, PARTICIPATION, LIQUIDITY
and SENTIMENT public envelopes. Bias imports no engine implementation, raw indicator,
SQL or network client. Aggregated copies/other dependency keys are rejected, so
underlying and MTF evidence cannot both be counted. Bias does not consume MTF results;
MTF can aggregate the resulting per-timeframe Bias without a cycle.

Core's dedicated Bias processor reads the normal runner's current indexed run
bindings and exact same-candle engine rows. It checks current producer/transitive
dependency generations, data epochs, feature generations, operator revision, public
versions/config/input signatures, identity, knowledge/publication times and quality.
A missing engine binding/checkpoint is a bounded wait, not a fabricated UNKNOWN row.
A genuine committed UNKNOWN/warmup engine result is admitted as missing evidence
for its role; it cannot become a neutral vote. All nine engine rows must exist for
the candle before the parent checkpoint advances, including optional families whose
classifications may remain unavailable.

The processor never invokes child classifiers/backfills. All numerical features and
previous engines remain unchanged. Minimal public inputs retain exact result refs,
only relevant flow/context fields, and no raw OHLC or full feature packets. Core
commits immutable inputs, results and state atomically to intelligence.db. Failed
parent computation leaves child history intact. Configuration/generation changes
create separate runs. Stored inputs replay exactly without current feature values.

Automatic processing uses the existing recent 32-candle seed, advanced to the latest
common dependency start if engines were initialized at different times. It follows
new closes and waits for children to catch up. Explicit older research requests are
bounded by those indexed dependency histories and report the common seed limitation;
they do not silently manufacture years of earlier Bias. Normal runner budgets and
optional MTF processing still apply. No new thread/scheduler or trading-event gate
is introduced.

## Directional evidence and correlation caps

All source scores are signed [-1,1]; unknown remains unavailable rather than zero.
Full directional budget defaults:

| Family | Budget | Admitted evidence |
|---|---:|---|
| Trend + Structure combined | .45 | Equal internal shares, capped together |
| Momentum | .25 | Confirmed signed direction times strength/100 |
| Observed executed flow | .15 | Complete observed 60-second aggressor imbalance |
| Confirmed Phase | .05 | Confirmed markup/markdown or confirmed cycle hypothesis |
| Independent sentiment | .10 | Reserved and unavailable in v1 |

Trend direction is multiplied by its strength/100. Structure contributes its
confirmed direction, not its "source completeness" strength interpreted as trend
power. Broken/developing structure and pending directional confirmations cannot vote.
Each source budget is multiplied by that source's valid coverage; directional
confidence uses the source's evidence confidence. Trend already incorporates
Structure, so their combined weight cannot exceed .45. Price/structure/momentum/phase
are not claimed statistically independent; their combined directional cap is .75.

Observed flow requires Liquidity's validated observed flow contribution, finite
imbalance and explicit source scope/association. It is not inferred liquidity-level
proximity, book imbalance, candle colour or sampled liquidation direction. Related
perpetual flow against spot candles remains explicitly labeled. Participation is
context, not a second copy of the same executed trades.

Sentiment v1 only has a funding/derivatives proxy. Positive funding is **not** an
independent directional advantage, so that .10 budget stays missing. It can inform
risk through its public risk output. Regime/Volatility have no signed directional
votes; their correlated ADX/EMA/ATR information is context rather than extra evidence
that magically creates agreement.

Score = sum of full-budget covered signed contributions, with no renormalization
when sources are missing. Require >=.60 directional coverage and at least two
available directional families before proposing a direction. Entry neutral deadband
is ±.15; an existing bullish/bearish state holds until crossing its ±.075 hold band.
Otherwise NEUTRAL represents enough measured evidence with no dominant net side;
insufficient evidence yields UNKNOWN. Require three consecutive closed proposals to
change the base bullish/bearish/neutral state. Missing evidence/gaps reset confirmation.

STRONG_BULLISH/STRONG_BEARISH additionally require absolute score >=.65, confirmed
base direction and context coverage >=.50. Strong intensity is not a safe entry or
calibrated probability. Its threshold is an intensity tier; persistence applies to
the underlying direction. Candidate intensity remains separate until confirmation.
Default maximum directional coverage is .90 while independent sentiment is absent.

## Context and risk

A separate context budget is Regime .30, Volatility .30, Participation .20, observed
execution Liquidity .10 and derivatives Sentiment risk .10. Only relevant known
confirmed context contributes; unknown book state is not execution coverage, and
unknown derivatives risk is not a safe-risk observation. Each admitted context
budget is multiplied by source coverage/confidence. Volatility's independent
confirmed shock may remain useful while other volatility dimensions warm up.

Risk escalates independently of direction:

- EXTREME: confirmed extreme volatility shock or public EXTREME derivatives stress.
- HIGH: moderate volatility shock, extreme volatility level, observed THIN/WITHDRAWING
  execution liquidity, or public HIGH derivatives stress.
- MODERATE: high volatility, regime transition/instability, low participation,
  invalidated phase hypothesis, or public MODERATE derivatives risk.
- Otherwise UNKNOWN. V1 does not infer LOW from missing sources, zero sampled
  liquidations or an otherwise quiet chart.

Use the maximum supported risk level and expose all reasons. Book/flow context keeps
its actual venue/market association; related perpetual conditions are not claimed to
be spot execution measurements. Risk classification is a transparent heuristic,
not portfolio loss probability or a guarantee that an opportunity is tradable.

## Alignment, scores and audit

Positive and negative point totals show agreement/conflict. Both >=.10 yield
CONFLICTED alignment; smaller two-sided evidence is PARTIALLY_ALIGNED; sufficient
one-sided or genuinely neutral evidence is ALIGNED. Insufficient directional coverage
is UNKNOWN. This describes admitted evidence, not completeness of all market inputs.

Agreement = abs(net points) / sum(abs(points)); genuine all-neutral evidence has
agreement one. Contradictory cancellation has agreement zero. Supporting/opposing
sources relative to the net preference, plus explicit bullish/bearish source lists,
remain visible even when cancellation gives NEUTRAL.

Strength = 100*abs(full-budget score), nullable without enough directional coverage.
Overall coverage = .8*directional coverage + .2*context coverage. Overall confidence
= .8*directional evidence confidence*agreement*confirmation progress + .2*context
evidence confidence, capped at coverage. These are transparent evidence scores,
not win probabilities. Directional/context components are exposed separately.
Reserved/missing budgets never increase the remaining sources' weights. V1 remains
PARTIAL because comprehensive independent sentiment/risk inputs are not available.

Confirmed classification changes emit stable-ID BIAS_TRANSITION events at current
knowledge time. Repeated identical states do not duplicate events. Preview returns
the old confirmed classification, UNKNOWN candidate, no new events and unchanged
state. Historical reconstruction retains publication-time assumptions explicitly;
future actual publications cannot enter an earlier live analysis.

## Operation

Pull and restart the existing runner. Bias populates automatically after compatible
base-engine publications/checkpoints are available. Optional diagnostics:

```bash
python3 run_regime.py --engine BIAS --automatic --summary --diagnostics
python3 aggregate_market.py --engine BIAS --symbols BTCUSDT --summary
```

The first synthesizes stored exact-candle dependencies; the second aggregates saved
Bias across timeframes. Neither creates BUY/SELL flags. MTF recognizes strong Bias
labels as bullish/bearish directional opposition while preserving per-timeframe
intensity. No UI, notifications, recorder or existing Decision/Confidence/Opportunity
behavior changes in this release. Predictive usefulness remains a separate research
question; passing software tests alone does not establish profitability.
