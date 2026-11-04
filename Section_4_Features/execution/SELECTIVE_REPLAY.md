# Calculation changes and historical replay

The existing runner owns all calculation and repair work. There is no additional
downloader or worker. Feature files remain in `Section_4_Features/features/`, one
file per numbered source section; the UI features and settings remain connected.

On runner startup, `components.py` fingerprints the trusted local Python
calculation statements, their indicator helpers, referenced constants and inputs.
It follows dependencies between calculations. RSI and ADX/DI are separate units
even though their numbered section shares a source file. Comments and formatting
do not change a calculation fingerprint.

- Display/style changes cause no calculation replay.
- A Section 8 strategy change does not invalidate Section 4 features.
- A calculation input or formula change repairs its outputs and downstream
  dependents, using unchanged prerequisites from stored feature columns.
- Shared helper or execution infrastructure changes can affect many calculations;
  all affected dependents must then be repaired.

For example, an RSI length edit updates RSI, previous RSI, RSI change and the two
momentum divergence outputs. It does not calculate EMA, ADX, volume profile or
zones. An ADX/DI edit also invalidates the current DI strategy's decisions. An RSI
edit leaves that strategy's decisions alone. Dependency selection for decisions
uses the strategy's declared input fields.

Repair uses bounded chronological batches, starting at the first stored raw
candle. Recursive/stateful calculations need their historical seed; changing EMA
or RSI cannot in general be corrected by changing just one candle. Only affected
SQL columns are updated. Unrelated historical values are preserved. Once repair
reaches the main checkpoint, the repaired running state is merged into it and
normal new-candle processing resumes. Normal new candles still calculate the
complete feature packet once.

The feature-column updates and partial checkpoint commit in one transaction.
Restart resumes the last committed batch. Editing or reverting an input during a
repair restarts the affected repair so partially changed rows are not abandoned.
Data deletion clears both partial and main state within the existing policy
guard. Failed batches retain their last committed checkpoint.

During repair, affected values beyond the partial cursor are withheld from API
results; unrelated values remain available. Dependent decisions are capped at the
repaired prefix and replay in order with the BUY/SELL alternation rule intact.
New closed-candle feature processing for that pair waits for its repair; market
downloads and other pairs continue through the existing scheduler. Live previews
retain their existing closed-checkpoint adjacency requirement.

`component_baseline.json` is the frozen source fingerprint for adoption of the
previous formula-v3 checkpoints. **Do not regenerate it for future formula edits.**
Existing matching checkpoints adopt metadata without recalculating or resetting
their cursor. Subsequent checkpoints store compact differences from this baseline.
Checkpoint version remains 3. Existing initial full-conversion backlog still needs
to finish: selective repair does not manufacture uncalculated feature history or
skip the original migration. Older rows can remain in the database while this
backlog runs, so row count/latest row is not proof of current-formula completion.

Fingerprints use a fixed AST representation on Python 3.12, 3.13 and 3.14. The
first selective-replay release used `ast.dump` defaults; Python 3.13+ omits empty
lists there, which incorrectly invalidated unchanged formulas against the 3.12
baseline. Recovery recognizes that exact old fingerprint of the current formulas,
retires formatting-only jobs and preserves the main checkpoint. Real input edits
still receive their selective repair. Completed old-format checkpoints adopt the
portable metadata without replay. Maintenance also recovers one queued old-format
job per visit outside the history owner, without calculating other symbols.

After editing calculation code or configured inputs, restart the existing runner.
No manual historical rebuild command is required. `check_coin.py SYMBOL --logs`
reports full replay checkpoints and any targeted repair's affected columns and
cursor. Turning features off in the display controls visibility, not the runner's
calculation requirements.

The component graph is built from local Python AST, not from database code or
remote Pine text. Feature code must use the existing explicit `e[...]`,
`e.previous(...)`, indicator sites and persistent-array helpers so dependencies
remain discoverable. New execution idioms need graph coverage and reference tests.

## Support/resistance lifecycle display

`zone_lifecycle.py` runs after the translated feature steps and exports
`sr_zone_events`: compact JSON deltas for births, changed bounds/classification,
and removals **after** the engine's existing merge/invalidation rules. Unchanged
candles store `[]`, rather than copying every live zone into every feature row.
Each change retains its previous geometry so a chart window can reconstruct
older active and retired zones from the current committed checkpoint. The
combined bars request optionally includes `sr_snapshot`; it performs no feature
calculations and opens no second market-data connection to the exchange.

The chart no longer treats a change in the *nearest* zone as an invalidation.
One identity retains a continuous stepped polygon as its bounds change; old
bounds are not rewritten retrospectively. Institutional promotion switches its
style without overlapping ordinary/institutional fills. Missing feature rows,
masked repair ranges, and raw history gaps stop claimed coverage. A forming
candle may extend an active band's display by one candle; it cannot invalidate
it. Existing no-border/color/opacity controls apply.

Old nearest-only rows do not contain enough information to reconstruct all
zone lifetimes. The new export therefore needs a one-time **S/R-only** historical
repair to the existing checkpoint, then normal chronological processing resumes.
The four corrected institutional touch normalizations and four institutional
band edges are also repaired selectively. EMA, DMI, RSI, VP and unrelated stored
columns are preserved; the current DI strategy does not depend on these fields.
The original full formula-v3 backlog, if present, still has to finish.

The numerical merge rules are unchanged: a new ordinary zone merges with the
nearest eligible zone within `srMergeDistance`, preserves the survivor's height,
and excludes institutional candidates. Similar-looking ranges can thus remain
different valid identities; the UI does not silently combine them or impose a
new maximum zone count. The source's reverse removal loops, parallel arrays and
NA propagation are covered by regression checks. Arrays are initialized by
`execution.memory.update`, before numbered feature functions run.

## Reusing selective plans

A Catalog caches at most 32 compiled selective plans by the set of changed
calculation-unit IDs. The same plan can read different per-pair parameters from
its Context; no indicator state or calculated outputs are shared between pairs.
A new Catalog has a separate cache key. Formula fingerprints and checkpoint
signatures are unchanged by this optimization, so installing it creates no new
historical replay. In a six-run local setup benchmark, median compilation was
48 ms uncached versus 0.004 ms for cached lookup. This measures plan setup only,
not production database throughput or total catch-up time. Targeted replay log
lines now include measured batch rows/s, including checkpoint/SQL overhead.

Persistent state has dependencies across candle boundaries. A writer near the
end of a feature step can affect readers near its beginning on the next candle.
The catalog includes these feedback edges and closes them when compiling a plan,
including a resumed repair's saved changed-unit set. Tests compare every affected
historical value and the next streamed packet after ATR/config/source changes.

### Order-block lifecycle repair

OB mitigation requires a candle strictly later than formation; breaker mitigation
requires a candle later than promotion. Both bounds must exist. OB ages are
calculated after promotion so inactive bounds and ages agree on that candle.
Strict qualification thresholds and same-candle structure confirmation remain
unchanged. The checked-in Pine reference mirrors these scalar corrections.

`obDisplayZones` checkpoints every still-valid normal/strict OB and breaker with
stable identities. New detections do not remove older zones. `ob_zone_events`
stores only formation, first subsequent overlap, promotion and invalidation
changes, with reversible prior state and terminal history. Promotion preserves
the originating OB's mitigation history and starts a fresh breaker return clock.
A candle can touch and invalidate a zone together; OHLC does not establish which
intrabar event came first. Invalidation is close below a bullish zone's low or
above a bearish zone's high; equality remains valid. Existing scalar contract
fields continue to describe the latest selected block for compatibility.

Adding the ledger repairs only its export; scalar corrections also repair their
OB/breaker dependents. Existing unaffected columns and the main replay cursor are
preserved. Replay reconstructs state chronologically and merges the repaired
ledger for subsequent live candles. It must finish before historical OB zones
are displayed; the UI reports pending coverage. No global formula-version bump,
second download, or whole-packet replacement is needed.

Settings → Features → Order Blocks has separate normal/strict bullish/bearish OB
and breaker visibility, Display score toggles/bulk controls, opacity and invisible
borders. Labels are formation displacement strength in ATR units (inherited by
the breaker), not a probability or an invented reaction score. Charts use sparse
events plus the committed checkpoint; missing/masked history is never extended
as if validity were established. No arbitrary zone cap silently deletes blocks;
processing cost scales with the number of still-valid zones.

### Keeping ready pairs current during long repairs

The bounded non-owner feature turn alternates between near-current eligible pairs
and the original historical round-robin service. Near-current means an existing
checkpoint with the current calculation signature, no targeted replay job, and
1–12 pending raw rows (checked with an indexed LIMIT 13 query). The raw historical
cursor still gates actual processing. The bulk owner's time/row reservation is
unchanged; repair jobs retain regular background turns.

This does not make an incompatible historical checkpoint safe for live use. A pair
whose targeted repair is in 2018 still needs that repair completed before current
stateful outputs/decisions can resume. No state is reset, no historical candles are
skipped and no provisional output is promoted to a confirmed trading signal.

### Optional recovery budget and pair preference

The default feature allocation remains 1 second / 1000 rows per maintenance turn.
For a long repair, the operator can increase its bounded allocation and prefer a
specific active pair without pausing coins, launching another writer, resetting
state or changing formula fingerprints:

```bash
python3 configure_feature_runtime.py --seconds 3 --max-bars 3000 \
  --priority-symbol BTCUSDT --priority-timeframe 5m
```

The existing runner reads settings at its next feature maintenance turn. The code
update itself requires one runner restart. Configuration is machine-local in
`Section_1_Global_Core/feature_runtime.json` (Git-ignored). This scheduling preference
never restarts historical replay or alters the epoch/formula signature. The
preferred pair gets the bulk feature allocation only while it has pending history,
a targeted job or an outdated signature. Other symbols **and other timeframes of
the preferred symbol** retain the existing bounded background share. Once caught up,
the normal bulk selector resumes; a later new candle may make that preferred pair
eligible again. Paused/inactive preferred pairs are ignored, not re-enabled.

This can increase CPU use and delay other runner phases. Budgets are soft between
bars and exclude some setup/commit overhead; they are not wall-clock guarantees.
Time is limited to .25–10 seconds and the row setting to 200–10000. Existing full
and selective batch caps still apply; a 3000-row setting is a maintenance budget,
not a promise that each SQL batch will contain 3000 rows.

Inspect settings or restore the original scheduling at any time:

```bash
python3 configure_feature_runtime.py
python3 configure_feature_runtime.py --reset
```

Full and selective feature batches now serialize checkpoints and materialize SQL
parameters before acquiring the market-data writer lock. Epoch/enabled validation
still occurs under that lock, and the rows and matching checkpoint commit in one
transaction. Serialization failure cannot publish a partially prepared batch.
Full logs distinguish `serialize`, `lock_wait`, and `db` (opening/writing/checkpoint
storage/commit); selective logs additionally separate `restore`, `read`, and
`compute` seconds. These measurements do not presume that lock delays are disk I/O.
Use actual laptop measurements to evaluate improvement; synthetic fixtures do not
establish a production speedup or an ETA for years of replay.
