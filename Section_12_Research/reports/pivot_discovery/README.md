# Pivot property study — BTC and SUI, 15 minutes

Open the running workspace at <http://127.0.0.1:8765/?input=default#pivot-title>.

From the project directory, launch or reopen it with:

```sh
.venv-build/bin/python3 Section_12_Research/cli/open_strategy_study.py
```

You can also double-click `Section_12_Research/launchers/Open Strategy Study.command` in the project folder.
This starts a local research server when necessary and reuses it when running.
It does not install a background service. The default input now reads BTC 15m
directly from memory. Choose any stored coin/timeframe with **Memory coin**,
**Memory timeframe** and **Read memory**. The earlier frozen BTC/SUI studies
remain separate snapshot choices in the input picker.

## Trailing sells and all-coin memory replays

The latest user-specified bearish DI50 three-candle reversal, its reviewable
workspace presets and measured results are in
[the DI50 study](../DI50_15m_three_candle_reversal/README.md).
Current/previous DI fields are searchable as **Previous DI+** and **Previous
DI−**; the candle controls spell out 0=current, 1=previous and 2=two ago.
The SELL action now also offers **Take profit** for the existing fixed 1%
bearish-Regime policy.

- On an existing SELL branch, choose **Sell action → Trailing SELL**, or add
  a branch with **+ Trailing SELL**.
- Set **Activate at net profit (%)** and **Trail below highest since entry
  (%)**. Defaults are 1% activation and a 0.5% trail. Branch conditions are
  additional requirements: for the bullish example, use `DI+ > 50`, so BOTH
  net profit ≥1% and the known DI condition must hold. Once armed, the trail
  remains armed, even if the condition later becomes false.
- The highest price is tracked from entry, including before arming. The
  standing 0.5% net loss budget remains active while waiting for the trail.
  Other regular SELL branches can still exit a position earlier.
- Choose **Within-candle price order** explicitly. Intrabar eligibility uses
  the previous closed candle's conditions. Newly true conditions at this
  candle's close may arm an order for the next candle; they never cause a
  retroactive exit inside the candle which just closed. High/low sequencing
  is an OHLC assumption, not a reconstruction of actual trades.
- Under **Coins to replay from memory**, select one or several coins, or use
  **Select all stored coins**. Coins execute sequentially with separate
  positions and starting capital. Each gets its own saved report; there is
  no combined portfolio-return claim. The batch uses one shared market-data
  cutoff; an individual coin's download delay can still limit its coverage.

Memory mode exposes every stored feature and ADCN column, plus scalar engine
classifications and outputs across stored timeframes. Use **Find a field** in
each condition to search the full catalog. It loads only requested columns
and compatible stored engine histories, in pages. It does not recalculate
indicators or reconstruct missing engine history. Feature replay / missing
historical outputs remain explicit unavailable inputs, rather than zero or
neutral. The recent chart inspector reads all stored columns for its bounded
window. Raw-only coin/timeframe scopes also appear, even while features wait.
Weekly and calendar-month candles have their actual calendar boundaries.

The live memory connection check found **51 stored coins, 743 feature columns
and 24 ADCN columns**. BTC and SUI chart responses and every selectable field
identifier were checked. Separate real-data replays were exercised in a
temporary validation workspace, without adding test runs to your saved runs.

Memory-mode pivot discovery starts with **Compare properties**; changing the
chart coin does not automatically scan its entire history. **Refresh input**
reloads current stored data and invalidates the discovery cache. No manual
export is needed to run a strategy against memory.

## How to use the study

1. Choose any stored coin/timeframe, or a frozen BTC/SUI 15m snapshot. The chart
   and discovery comparison use that input.
2. Choose BUY/lows or SELL/highs, a Regime and a Trend. Each refers to the
   selected chart timeframe. Optional dates use Pakistan time.
3. Compare qualifying pivots with **Other candles** or **Pivots below 1%**.
4. Inspect features at offset −1, 0 or +1 separately. Offset 0 is the
   pivot candle; +1 is the following candle. Click **Show on chart** for a case,
   or click any chart candle to inspect its stored features and context.
5. Click a feature in **Feature differences** to plot it under price.
   **Overlapping feature conditions** shows coverage of predefined DI, RSI,
   volatility and candle conditions in the two groups.
6. Use the AND/OR strategy editor with regular or trailing SELL actions.
   Memory and new snapshot inputs apply a standing 0.5% net stop budget.
   Trailing branches also enable that budget on legacy snapshots. Prior
   experimental strategies are not automatically enabled.

## Reference labels and comparison

**Pivot definition:** these are the base swing confirmations emitted by
`Section_4_Features/features/market_structure.py`, before the later
`validPivotHigh` / `validPivotLow` structural qualification. Only one candidate
side is active. A later closed candle confirms a high after a 25% retracement
of its rise from the preceding confirmed low, or confirms a low after a 25%
recovery of its decline from the preceding confirmed high. Confirmation
immediately seeds the opposite candidate using that confirmation candle's
opposite extreme. Consequently adjacent origin candles are allowed, although
their confirmations occur sequentially. The original Pine contains the same
rules. There is no minimum 1% move or multi-bar pivot spacing in that function.
The chart places markers at origin candles, not at confirmation times.
See `PIVOT_DEFINITION_AUDIT.md` and `pivot_sequence_audit.json`.

Use the later-confirmed native pivots as the historical reference standard.
BUY reference success means the **first strictly later native pivot high** is
at least 1% above the native low. SELL reference success describes the reverse
decline after a high, for studying exits in a spot strategy. It is not a short.
The endpoint prices must match stored OHLC extremes; gaps censor the swing.
The final swing without a known opposite pivot remains censored.

Compare reference-candle features with controls matched 1:1 within the same
UTC year, exact same-timeframe Regime primary/direction and Trend direction.
Samples within each group are selected deterministically and evenly over time.
Insufficient controls leave explicit unmatched references. Missing values are
reported as missing; they do not become zero or neutral. UNKNOWN context is
its own stratum. Feature differences are exploratory associations.

The pivot-property comparison contains 31 numeric measurements/derived properties.
The original frozen inputs retain 87 stored feature columns; memory inputs
expose the entire current stored schema. The original frozen projection is
an initial research projection, not an evaluation or removal of every feature
in memory. Signed `close_to_ema50_pct` / `close_to_ema200_pct` are explicitly
derived as `100 * (close / EMA - 1)` and do not reuse the legacy stored
absolute-distance fields.

## Frozen data and first findings

Both snapshots end at **14 November 2026, 18:15 PKT**, including the closed
18:00–18:15 candles. Feature generation is 1.

| Input | Candles | Native pivots, both sides | Low → immediate high ≥1% |
|---|---:|---:|---:|
| BTCUSDT 15m | 323,568 | 103,330 | 15,774 |
| SUIUSDT 15m | 123,941 | 37,126 | 11,559 |

Over the common period starting **3 May 2023, 17:00 PKT**:

| Input | Resolved native lows | Low → immediate high ≥1% | Reference rate |
|---|---:|---:|---:|
| BTCUSDT 15m | 18,437 | 3,383 | 18.35% |
| SUIUSDT 15m | 18,563 | 11,559 | 62.27% |

These describe reference swings, not trading win rates or fills at the lows.
The common-period observations support investigating SUI's larger relief
swings; they do not establish that every large dip rebounds sufficiently.

Against ordinary candles matched by year and context, successful lows on both
coins have larger lower wicks, more preceding downside movement and wider
ranges relative to ATR. Against failed lows in bearish and transitional
bearish conditions, volatility and distance below EMAs stand out. For example:

| Transitional bearish: qualifying vs failed low medians | BTC | SUI |
|---|---:|---:|
| NATR, percent | 0.604 / 0.344 | 0.776 / 0.509 |
| Close relative to EMA50, percent | −0.862 / −0.373 | −1.294 / −0.734 |
| Previous 12-bar close return, percent | −0.884 / −0.342 | −1.229 / −0.648 |

DI− and RSI extremes occur more often at qualifying lows, but do not cover
most of them. Across all regimes, only 9.68% of matched BTC qualifying lows
and 7.67% of SUI qualifying lows have DI− ≥40 at the pivot candle. This is
one candidate family, not a universal description of successful lows.
Offset +1 should be studied separately for the spread peak/drop confirmation.

Full descriptive results: `initial_findings.json`.

## Calculation progress and provenance

At the recorded runner check, both BTC/SUI 15m live Regime, Trend, Structure,
Momentum and Volatility outputs were VALID. Downloads and committed features
were caught up, without a feature replay job. Historical engine calculation
remained separate: BTC Regime 127,200 classified / 196,368 pending;
SUI Regime 160 classified / 123,781 pending. SUI's historical Trend had 100
classified and Structure 300. See `runner_readiness.json` for the exact check.

For this study, the existing current STRUCTURE → TREND and REGIME engines were
replayed offline from each instrument's first stored candle. They use the
same timeframe and stored measurements; this is reconstructed historical
context, not a claim about original live publication time. No production
engine outputs were written. SQLite read transactions are released after
each export page and before the offline replay.

The generic source's rule replay models next-open entries, configured costs
and the 0.5% net stop budget. OHLC cannot give an exact stop-touch timestamp;
adverse opens use the modeled actual open without clipping the loss. Missing
price intervals censor execution. The legacy BTC 1h input retains its earlier
signal-only replay and is labeled accordingly in the workspace.

To regenerate a current research input:

```sh
.venv-build/bin/python3 Section_12_Research/cli/export_pivot_candles.py --symbol SUIUSDT --timeframe 15m --output Section_12_Research/reports/pivot_discovery/SUIUSDT_15m_source.json.gz
```

Then press **Refresh input**. The study is a frozen snapshot, not a live feed.

## Verification

67 current targeted unit/integration checks passed, including compact input loading,
15m time alignment, native label validation, missing observations, signed EMA
distance, date filtering, matching, chart endpoints, memory column projection,
missing-history handling, independent multi-coin replays, trailing conditions,
permanent arming, OHLC order assumptions, costs and adverse-open stops.
The running workspace served BTC and SUI charts and comparisons successfully;
see `workspace_verification.json`. Native browser inspection was unavailable,
so visual layout has not been confirmed through computer use.

No live strategy, feature formulas, ADCN values or memory retention were
changed by this study.
