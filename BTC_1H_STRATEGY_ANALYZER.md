# BTC 1h candle strategy analyzer

`analyze_btc_hour_strategy.py` evaluates rule expressions on **every stored closed
hourly candle**, without conditioning on candidates, successful native pivots or
future outcomes. It is an offline research tool. It does not change production
strategy rules, the runner, checkpoints, alerts or databases.

Several BUY branches and several SELL branches feed **one** alternating sequence:

1. Start flat, waiting for BUY. Ignore SELL matches until the first BUY.
2. Accept the oldest candle matching any BUY branch. Ignore all subsequent BUY
   matches until a SELL qualifies.
3. Accept the oldest qualifying SELL, then wait for BUY again.
4. Evaluate conditions at candle close and fill at the next contiguous valid
   candle open. One accepted signal per candle. If multiple branches qualify for
   the required side simultaneously, configuration order chooses the primary
   branch; all matching IDs and their input values are recorded.

The analyzer does not reset this state at a year boundary or a price gap. Missing
prices censor affected trade returns instead of creating an artificial SELL or
allowing a second BUY. Shortened historical candles are explicitly invalid, not
silently promoted to complete hours. End-of-window orders without a next candle
are unfilled/censored; a filled BUY without SELL stays open. No final liquidation
is invented.

## Run the supplied example and baseline

From the repository root, with Python 3.12 (standard library only):

```sh
python3 analyze_btc_hour_strategy.py \
  --input research_reports/BTC_1h_sequences/source_v1.json.gz \
  --config research_reports/BTC_1h_sequences/strategy_configs/multi_branch_v1.json \
  --baseline-config research_reports/BTC_1h_sequences/strategy_configs/di_baseline_v1.json
```

The example has four five-condition branches for up/down context, on both sides.
It combines independent DI turns, DI dominance, spread, RSI, and either stored
local Trend direction **OR** a price/EMA50 comparison. The OR is an explicit
alternative, not an automatic substitution for missing engine context. EMA50
position and the versioned Trend engine are different measurements. Example
thresholds are fixed demonstration assumptions, not optimized or recommended
trading rules.

The command saves `strategy_analysis.json.gz` and a self-contained
`strategy_analysis.html` under `research_reports/BTC_1h_sequences/strategy_analyzer/`.
The dashboard exposes the complete sequence, yearly results, branch diagnostics,
successful/failed/open/censored trades, revision cohorts and individual signal
inputs. It has no CDN dependency. Original source and earlier research reports
are preserved. Commands do not commit or push.

Execution defaults are 4 bps fee and 2 bps slippage per side, starting with 100
units of capital. Configure them under `execution`. Success means a completed
spot BUY-to-SELL trade with **net return >0** after these costs; zero-return
trades are separate. There are no shorts, protective stops, position sizing rules
or time exits unless an exit is expressed as a SELL rule. Closed-trade balance
compounds the full balance across completed trades only. Censored/open trades are
excluded; this is not a complete account equity curve. Reported drawdown is at
closed trades, not the worst intratrade drawdown. Profit factor uses gains/losses
in that closed-trade balance; the separate trade-return profit factor uses sums
of per-trade return percentages.

## Expressions and available memory

A configuration contains a version, an id, execution parameters and a list of
branches. Each branch has a unique `id`, `side` and a `when` expression:

```json
{
  "id": "example_buy",
  "side": "BUY",
  "when": {
    "all": [
      {"field": "event.di_minus_peak", "op": "eq", "value": true},
      {"field": "di.abs_spread", "op": "gte", "value": 10},
      {"field": "feature.rsi", "op": "lt", "value": 40},
      {"any": [
        {"field": "context.4h.TREND.direction", "op": "eq", "value": "BULLISH"},
        {"field": "context.1d.REGIME.primary", "op": "eq", "value": "RANGING"}
      ]}
    ]
  }
}
```

`all`, `any` and `not` nest explicitly; there is no string evaluation or hidden
operator precedence. Any number of branches/conditions is supported, including
four/five-condition strategies. Leaf operators: `eq`, `ne`, `gt`, `gte`, `lt`,
`lte`, `in`, `available`, `missing`. Numeric comparisons require numeric values.
Stored SQLite 0/1 feature flags should be compared to numeric 0/1; event fields
are actual booleans.

Fields:

- `feature.<column>`: any scalar stored feature included in the source export.
- `price.open`, `price.high`, `price.low`, `price.close`, `price.volume`.
- `di.di_plus`, `di.di_minus`, `di.abs_spread`, `di.signed_spread`,
  `di.dominance`, `di.dominant` (PLUS/MINUS/BALANCED), `di.adx`.
- `event.di_minus_peak`, `event.di_plus_peak`, `event.spread_peak`,
  `event.di_only_buy_turn`, `event.di_only_sell_turn`. Strict three-close turns
  are known only at the third close, with no hindsight pivot selection.
- `context.<1h|4h|1d>.<ENGINE>.<classification field>` for compatible exported
  Section 5 histories, including Regime, Trend, Bias, Liquidity and other engines.
  Only the exact last-closed candle is usable; VALID/PARTIAL quality is required.
  Classification UNKNOWN remains unavailable. These histories reconstruct
  close-time knowledge, not proof of original live publication.

Use `other_field` instead of `value` to compare two stored measurements:

```json
{"field":"price.close","op":"gte","other_field":"feature.ema50"}
```

Optional `lag` and `other_lag` reference 0–1000 **past** candles, requiring a
contiguous path. Negative/future lags and outcome/result fields are rejected.
Inputs absent from an older export remain unknown and are listed in diagnostics.

Missing data uses three-valued logic: false AND unknown is false; true OR unknown
is true; otherwise an unresolved expression is unknown and cannot trigger a
signal. NOT unknown remains unknown. `available`/`missing` explicitly test
availability. Per-branch unknown counts and overlapping field/reason counts are
reported, including missing operands of expressions that resolved via another OR
branch. Missing values are never silently replaced with zero or neutral labels.

### Refresh all features from the machine holding market memory

The frozen uploaded source contains only its originally exported columns and
history. To read all currently stored feature columns, first create a fresh
read-only cohort report, then export/replay it:

```sh
python3 study_pivot_moves.py --symbol BTCUSDT --timeframe 1h \
  --threshold-pct 1 --context-cases 0 \
  --output research_reports/BTC_1h_sequences/current_cohort.json.gz

python3 analyze_btc_hour_strategy.py \
  --report research_reports/BTC_1h_sequences/current_cohort.json.gz \
  --config research_reports/BTC_1h_sequences/strategy_configs/multi_branch_v1.json \
  --baseline-config research_reports/BTC_1h_sequences/strategy_configs/di_baseline_v1.json \
  --output-dir research_reports/BTC_1h_sequences/current_strategy
```

The pivot report establishes a consistent source generation/cutoff only. Native
pivot membership and outcomes never gate analyzer observations. Generation
changes are rejected instead of mixing incompatible memory. The fresh row export
is saved as `memory_source.json.gz` for repeatable offline work. No features are
recomputed, no history is backfilled, and no live database is written.

## Refine failures while checking preserved successes

Keep the first report/config as a baseline, edit a new configuration, then replay
the **entire** same input and compare:

```sh
python3 analyze_btc_hour_strategy.py \
  --input research_reports/BTC_1h_sequences/source_v1.json.gz \
  --config /path/to/revision.json \
  --baseline research_reports/BTC_1h_sequences/strategy_analyzer/strategy_analysis.json.gz \
  --output-dir research_reports/BTC_1h_sequences/strategy_revision_2
```

Alternatively, `--baseline-config` replays both versions on the exact same memory.
Comparisons require identical input fingerprints, window and execution costs.
New exports with different memory must replay both configs, not compare a stale
report. Each report retains the complete config, run id and source provenance.

The dashboard can isolate baseline failed cases **after** complete replay. It
reports successes preserved/lost/unresolved; failures corrected/removed/persisted/
unresolved; breakeven/unresolved baseline cases; and new entries. Trades are
matched by accepted BUY knowledge time. A corrected failure retains that BUY and
now closes profitably. A removed failure is reported separately, not counted as
an improvement in profit; shifted entries are removed plus new. Changing an early
signal can change all later alternations, so a failure-only replay is not used to
claim overall performance. Baseline outcomes are never valid trading predicates.

Optional `--since 2025-01-01T00:00:00Z --until 2026-01-01T00:00:00Z` selects
candle **knowledge times**, inclusive/exclusive, starting flat. Earlier candles
can supply already-known lag/turn context; fills require the next candle to be
inside the selected replay. Yearly results carry state continuously across years
and assign completed trades by SELL fill UTC year. Research periods already
inspected are not untouched holdouts. Freeze a revision before testing it on a
later uninspected period.

Validation:

```sh
python3 -m unittest discover -s tests -p 'test_strategy_analyzer.py' -v
python3 -m unittest discover -s tests -p 'test_hour*.py' -v
PYTHONPATH=. python3 tests/browser_strategy_analyzer.py
```
