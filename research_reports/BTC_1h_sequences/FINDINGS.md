# BTC 1h: every-pivot DI sequence findings

Source: `source_v1.json.gz`, uploaded in commit `d6a7940`. Coverage: 17 August
2017 09:00 to 5 November 2026 21:00 Pakistan time. There are 80,692 closed
candles, 25,893 native pivots, 25,918 candidate phases and 80,690 active candidate
candle observations. Five native pivots cannot be linked to a candidate phase;
they remain in the cohort. There are 31 measurement-gap flags and 10 initial
candles without both DI values. Missing/gapped observations are not zero-filled.

The findings come from the full exported sequence, not selected examples.
`findings_v1.json` contains the exact denominators, horizon statistics, medians,
year splits, context coverage and original/raw outcome discrepancy.

## What the study establishes

The useful distinction is **where an event occurs in the candidate's life**.
A first candidate, an updated extreme, a DI pressure turn, a spread turn and
native confirmation are different observations. Their timing and market response
cannot be collapsed into one simultaneous trigger. The data supports researching
these as separate states; it does not establish a profitable execution rule.

## 1. DI pressure does not normally peak on the first candidate candle

| Native pivot side | Candidates with DI turn evaluable | Pressure peak recognized at candidate start | Recognized at origin close | Recognized at native confirmation |
|---|---:|---:|---:|---:|
| LOW / BUY research point | 12,919 | 664 (5.14%) | 2,167 of 12,930 (16.76%) | 7,377 of 12,925 (57.07%) |
| HIGH / SELL research point | 12,912 | 512 (3.97%) | 2,150 of 12,931 (16.63%) | 6,787 of 12,930 (52.49%) |

BUY pressure means the independent DI− three-close peak; SELL pressure means
DI+. A peak is recognized at the third close. The denominators vary by stage
because gaps/warmup can make the turn unavailable.

Across candidate start through native confirmation, both a pressure peak and
a spread peak occurred for 9,365 lows and 9,134 highs. The first pressure peak
coincided with its nearest spread peak in only 5,462 and 4,441 cases respectively.
The remaining 3,903 and 4,693 had different recognition candles. This pairing is
a descriptive timing comparison, not a new trigger or a claim of causation.

For lows, a DI− peak had already been recognized within the candidate phase by
the origin close in 4,178 cases. Of the resolved cases, 70.11% subsequently had
the native 1% upswing, versus 61.40% without that observation. This is conditioned
on retrospectively identified native pivots; it is not an early-entry win rate.

## 2. Very high spread marks movement, not a safe immediate reversal

Among eventual native pivots, the share reaching 1% before the next opposite
pivot rises with spread at candidate start:

| Absolute DI spread | LOW: 1% upward swing / resolved | HIGH: 1% downward swing / resolved |
|---|---:|---:|
| Below 5 | 2,174 / 3,601 = 60.37% | 2,133 / 3,547 = 60.14% |
| 10–20 | 2,696 / 4,124 = 65.37% | 2,678 / 4,183 = 64.02% |
| 20–35 | 1,318 / 1,854 = 71.09% | 1,304 / 1,870 = 69.73% |
| 35–40 | 111 / 149 = 74.50% | 100 / 133 = 75.19% |
| 40 or higher | 89 / 101 = 88.12% | 95 / 110 = 86.36% |

These are hindsight swing labels measured from the extreme, not entry prices.
The causal observation check gives a very different result. On **all active
candidate candles**, from next open to the twelfth future close:

| Observation | Complete windows | Mean gross directional close movement |
|---|---:|---:|
| BUY candidate, spread below 5 | 8,563 | +0.056% |
| BUY candidate, spread 10–20 | 11,130 | +0.084% |
| BUY candidate, spread 35–40 | 819 | −0.173% |
| BUY candidate, spread ≥40 | 709 | −0.418% |
| SELL candidate, spread ≥40 | 920 | −0.596% |

BUY directional movement is price rise; SELL directional movement is price
decline, so the last row means price rose on average. SELL here is exit/rebuy
research, not a short-trade return. Observations overlap and include consecutive
candidate updates. This is not a unique-entry backtest.

Thus **spread ≥40 alone is not evidence to buy a low candidate or sell a high
candidate immediately**. A large swing can develop while the candidate keeps
extending against the proposed reversal. High-spread subsets are also small at
the native-candidate-start level. Fixed spread bins were descriptive assumptions.

## 3. The two DI+ recovery paths differ, but neither is a reliable trigger alone

There are 16,897 strict DI+ down-runs and 16,871 observed strict recoveries.
Unrecovered, plateau-ended and gap-ended runs remain separately recorded.
The following results begin at next open after the first DI+ up-tick and end
12 candles later. They use all recoveries, without selecting successful pivots:

| Path during dip through first recovery | Complete windows | Mean gross price return | Median return |
|---|---:|---:|---:|
| DI+ stayed above DI− and absolute spread | 6,572 | +0.141% | −0.039% |
| DI+ lost DI−, retained spread comparison | 2,674 | +0.003% | −0.024% |
| DI+ lost both comparison levels | 1,032 | −0.007% | +0.087% |
| DI+ was not above both initially | 6,524 | −0.027% | +0.028% |

For **brief one/two-bar dips**, preserved-control recoveries have a +0.131%
mean but a −0.009% median over 4,004 complete windows. Losing DI− alone gives
−0.059% over 601; losing both gives −0.044% over only 29.

Preserved control is worth retaining as a continuation-context event. It is not
a promise that price goes up: only 3,199 / 6,572 (48.68%) of all preserved-control
windows had positive close returns. Their positive mean is tail-sensitive. The
all-hourly baseline mean is +0.073% over the same 12-hour horizon, using 80,306
complete active-candidate candle windows.

The result also varies by year. Preserved-control mean returns are −0.009% in
2025 (697 complete windows) and +0.066% in 2026 (620), with negative medians in
both. These chronological slices were inspected after the full sample; they are
not untouched holdouts.

Restricting recoveries retrospectively to within 12 hours after native high
origin closes weakens the preserved-control result to +0.079% mean and −0.080%
median over 5,626 complete windows. Both candidate-start and origin-close
associations, and both fixed/next-opposite windows, remain in the export.

Regaining the **pre-dip DI+ value** is a different event from the first up-tick.
Of 6,597 preserved-control recoveries, 4,252 regained that value within the
specified recovery search, 2,333 did not, and 12 searches were censored.

Absolute spread is mathematically dependent: while DI+ > DI−, spread cannot
exceed DI+. Losing the spread comparison implies DI− > 2 × DI+. These are
separate path labels, not independent votes to inflate confidence.

## 4. Raw DI/ADX values differ between successful and failed swings

Medians at the origin candle close, separately by retrospective native outcome:

| Native outcome | DI+ | DI− | Absolute spread | ADX |
|---|---:|---:|---:|---:|
| LOW with subsequent 1% upswing | 15.93 | 24.00 | 12.32 | 29.63 |
| LOW without 1% upswing in completed swing | 17.72 | 20.90 | 8.98 | 25.54 |
| HIGH with subsequent 1% downswing | 21.40 | 18.11 | 11.33 | 29.59 |
| HIGH without 1% downswing in completed swing | 20.37 | 18.02 | 8.85 | 25.56 |

At low-candidate phase start, DI− dominance corresponds to a 67.33% resolved
native-swing hit rate, compared with 60.51% for DI+ dominance. However, at high
phase start, DI− dominance gives 64.55% versus 61.74% for DI+ dominance. The
broad symmetric dominance rule therefore does not characterize both early
candidate stages equally well. Stage and path matter.

These distributions overlap; their medians are not proposed numerical gates.
The archived score export has **zero non-null rows**. Raw DI values and normalized
dominance are measurements, not a calibrated DI confidence score. This study
cannot validate Confidence/Opportunity scoring from absent saved score records.

## 5. Native confirmation is often too late for a 1% objective

Median native confirmation is two hours after the extreme candle's opening
timestamp. The final candidate extreme is first recorded at its own candle close,
usually one hour after that opening timestamp. Candidate phase start is earlier
than the final extreme observation in many cases; it does not identify which
candidate will become the final pivot in real time.

By native-confirmation close, price was already at least 1% away from the
eventual extreme for 4,352 / 8,307 successful lows (52.39%) and 4,089 / 8,206
successful highs (49.83%). Even at the origin candle's close, that was true for
2,120 lows (25.52%) and 1,594 highs (19.42%). These measure displacement at the
observed close, not whether the 1% target touched earlier and retraced.

This supports testing earlier candidate/DI sequences. It does not make the
unknown intrabar extreme an executable entry or guarantee the move remains.

## 6. Full-history Section 5 context is not present yet

At linked candidate starts, out of 25,888 native pivots:

| Context | Regime present | Trend present | Bias present | Liquidity present |
|---|---:|---:|---:|---:|
| 1h | 17 | 17 | 8 | 13 |
| 4h | 45 | 45 | 39 | 45 |
| 1d | 209 | 209 | 206 | 209 |

Daily counts reuse the same daily result across several hourly pivots; they are
not independent daily samples. Liquidity and Bias rows are PARTIAL. We cannot
honestly claim a full-history regime-conditioned advantage from this coverage.
All available results are joined at exact last-closed times; missing history is
unavailable. The legacy structure defect identified earlier is not bypassed by
calling old labels equivalent to the independent engines.

BTC instrument Bias is not industry/sector bias; no sector breadth feed is
present. Structural liquidity is inferred, not actual resting-order measurement.
No historical order book is invented from current observations.

## Integrity and next research step

One archived 2017 high was CENSORED with a gap, whereas the newly exported raw
path yields HIT. Both outcomes are retained; all groups above use the exported
raw path. The export alone does not establish why the older gap differs. The
study continues with this explicit discrepancy rather than silently altering the
source or asking production to replay its history. Every pivot price is also
checked against its raw candle extreme.

The next candidate should be a finite sequence: candidate confluence; independent
pressure event; independently timed spread behavior; separate preserved-control
continuation and control-loss reversal paths. Do not turn a candidate, an isolated
DI fluctuation or spread ≥40 into an unconditional trade. Before choosing gates,
compare matched cohorts by year and volatility, acquire compatible historical
Section 5 context through an isolated research replay, and test a fixed rule with
spot fees, bounded positions and exits on a new chronological period.

The +0.141% preserved-control mean is **not** established executable net profit.
No costs, trailing stops, capital, order fills or position rules are simulated.
Touch rates can include both +1% and −1% in a single window; OHLC does not resolve
their intrabar order. None of these tables is a calibrated probability of profit.

Reproduction:

```sh
python3 study_btc_hour_sequences.py --input research_reports/BTC_1h_sequences/source_v1.json.gz
python3 summarize_btc_hour_sequences.py
```

For the full every-pivot visual report, expand `analysis_v1.html.gz` using
`gzip -dk research_reports/BTC_1h_sequences/analysis_v1.html.gz` and open the HTML.
