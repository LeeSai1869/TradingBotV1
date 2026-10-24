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
