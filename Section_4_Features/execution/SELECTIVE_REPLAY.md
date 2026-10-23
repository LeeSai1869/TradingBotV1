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

After editing calculation code or configured inputs, restart the existing runner.
No manual historical rebuild command is required. `check_coin.py SYMBOL --logs`
reports full replay checkpoints and any targeted repair's affected columns and
cursor. Turning features off in the display controls visibility, not the runner's
calculation requirements.

The component graph is built from local Python AST, not from database code or
remote Pine text. Feature code must use the existing explicit `e[...]`,
`e.previous(...)`, indicator sites and persistent-array helpers so dependencies
remain discoverable. New execution idioms need graph coverage and reference tests.
