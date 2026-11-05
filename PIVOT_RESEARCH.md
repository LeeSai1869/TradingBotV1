# Historical pivot move study — v1

Purpose: inspect historical pivots followed by at least 2% directional price
movement, then compare the surrounding bars/features before designing more
strategy rules. This tool does not change BUY/SELL, stops, features or the runner.
It is descriptive research, not a backtest or a causal explanation.

## Agreed selection

Use existing Section 4 confirmed structural pivot events; do not create a new
pivot detector. Default swing endpoint is the next opposite pivot by origin:
LOW to next HIGH for BUY_SIDE; HIGH to next LOW for SELL_SIDE. SELL_SIDE describes
a decline/possible avoided loss for spot, never short profit. Native confirmation
and source/version identity are retained.

For every pivot, retain:

- Original pivot price/time, detection candle and close-time knowledge timestamp.
- Maximum favorable and adverse movement through the opposite pivot, including
  wick touches; first closed bar whose high/low demonstrates the 2% move and how
  many bars that took. The origin candle itself is excluded because OHLC does not
  reveal the ordering of its high and low.
- A separate after-known benchmark starting at the next available candle OPEN at
  the knowledge boundary. This uses no future pivot price as an entry. If the
  swing ended before confirmation, report NO_POST_CONFIRMATION_WINDOW.
- Whether the origin's 2% move was already reached by confirmation.
- Complete non-hits plus partial/missing-data outcomes. A gap stops measurement
  rather than inventing a path; a hit observed before a later gap remains marked
  HIT with incomplete coverage. A tail without a next opposite pivot is partial.

The next opposite pivot and cohort selection deliberately use hindsight. These
are examples to inspect, not signals we claim were available at the turning
point. Known times reconstruct closed-candle knowledge, not actual publication
latency. Candle high/low cannot establish intrabar execution, stop-vs-target
ordering or net trading profitability. Do not treat future context as a past
input or infer cause merely from a feature pattern appearing near a pivot.

## Generate and immediately publish the full-history cohort

Run on the machine holding the production candle/feature databases, from main:

```sh
git pull --ff-only origin main &&
python3 study_pivot_moves.py \
  --symbol BTCUSDT --timeframe 15m \
  --threshold-pct 2 --until 2026-11-05 \
  --before-bars 12 --after-bars 24 \
  --output research_reports/BTCUSDT_15m_all-history_2pct_pivots_v1.json.gz \
  --push-report
```

No `--since` means all available history through the committed current-formula
feature prefix, not the last 1,000 candles. The report records actual coverage,
source identity and the snapshot cutoff; replay/missing lineage blocks the scan.
The command streams raw price paths and prints progress. It runs manually,
outside the live scheduler, and never recalculates or writes market features.
It can take time on large histories and competes for local read/CPU resources.

`--push-report` commits only the generated artifact and pushes origin main. It
requires output under this repository's research_reports folder and the main
branch. It does not stage databases or unrelated files. If generation fails,
no report is published. Existing baseline reports are not overwritten if a new
filename is used. Date-only bounds are UTC midnight.

## All pivots, bounded feature duplication

The cohort report indexes ALL qualifying native pivots, including failures and
partial outcomes; it is not a recent-window or winners-only sample. To avoid
copying the entire feature database into Git repeatedly, it embeds full feature
windows for up to 20 evenly spaced origin-HIT cases and 20 complete origin-NO_HIT
controls (fewer if not available). These are descriptive examples, not a random
statistical sample. `--context-cases` changes the number per group; 0 produces
only the full cohort index. Gzip output is deterministic for unchanged inputs.

Each embedded case includes every stored feature column, OHLCV and availability
labels. Windows cover both the original pivot and its detection candle, taking
12 bars before and 24 after each anchor by default and merging overlaps.
Missing/incompatible/nonfinite values remain unavailable, not fabricated zeros.
All stored columns can include legacy fields; inspect their provenance before
using them to build a model. No engine-classification or external order-flow
coverage is invented where it was not recorded.

## Visual inspection

After updating, restart the UI backend and hard-refresh. In **Analysis**, find
**Historical pivot moves ≥2%** and load the generated .json.gz file.

- Filter origin hits, after-known hits, complete non-hits or all pivots.
- Inspect a case to see its before/after candle table, DI+/DI-/ADX/RSI/ATR and
  structure. A small interactive feature chart plots DI+/DI-/ADX by default;
  selecting another numeric feature plots that value across the context.
  The additional-feature selector exposes any stored column; each
  candle's All features expansion exposes its complete stored values.
- Show pivot on chart navigates the existing chart and marks the retrospective
  pivot, its confirmation candle and the 2% reference level. The overlay does
  not alter price scaling or production markers.
- Embedded windows are frozen in the report and can be read without another
  database request. Unsampled cases load on demand from the local store, with
  feature-generation/config/schema checks and the original report cutoff.
- Changing the before/after counts requests a new bounded context. Save case JSON
  downloads that case for review. A changed source generation requires a new
  cohort; the UI reports the mismatch instead of mixing feature versions.

The price chart remains your existing chart. Hide the experimental BTC strategy
flags if you want to inspect pivot research without those signals overlaid.

To export and publish a specific unsampled case from a report:

```sh
python3 study_pivot_moves.py \
  --report research_reports/BTCUSDT_15m_all-history_2pct_pivots_v1.json.gz \
  --case-id CASE_ID_FROM_REPORT \
  --before-bars 12 --after-bars 24 \
  --output research_reports/BTCUSDT_selected_pivot_context.json.gz \
  --push-report
```

The full report can be reviewed after push, including the embedded feature
examples. Actual BTC outcomes cannot be calculated in a workspace without the
user's market databases. First inspect the selected moves; compare equivalent
non-hits before proposing momentum-shift rules, then evaluate those rules on
separate chronological data. No statistical or causal claim is made here.

The browser viewer accepts up to 256 MiB of expanded JSON and 200,000 cases per
file. The scanner has no 1,000-candle cap. For larger 1m/5m histories, use fixed
chronological report ranges or fewer embedded contexts for browser inspection.
The supplied 103,127-case BTC 15m report expands to about 171 MiB.
