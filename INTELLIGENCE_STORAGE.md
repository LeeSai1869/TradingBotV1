# Intelligence result storage

`engine_results.payload` contains the full classification. Its `deterministic`
column previously duplicated that JSON, omitting only `computed_at` and
`available_at`. New writes keep a 71-character `sha256:` checksum in that column.
Same-key divergence checks accept both formats; readers continue using `payload`.
This storage-only change does not change run identities, classifications, inputs,
dependency references or checkpoints. Reload the runner to activate the new writer.

Existing rows are not rewritten when opening the database. Preview a bounded
sample with:

```sh
python3 deduplicate_intelligence.py
```

After updating all writers, replace verified duplicate copies in small transactions:

```sh
python3 deduplicate_intelligence.py --apply --max-rows 10000 --time-budget 10
```

Each committed batch prints its cumulative counts and `last_rowid`. Resume with
`--after-rowid <last_rowid>`. Repeating a range is safe; checksum rows are skipped.
A legacy duplicate that disagrees with the full result aborts and rolls back its
whole batch. Preserve the last successfully printed cursor if a later batch fails.
No classifications, source inputs, old generations or checkpoints are deleted.

`json_bytes_removed` counts duplicate JSON bytes replaced by checksums; it is not
a physical disk-space estimate. SQLite can reuse freed overflow pages, while the
database file may retain its size. Physical shrinking needs a separate compaction
operation with sufficient working space. This command does not run `VACUUM`,
restart services or prune analytical history. Historical backfill still stores new
results and inputs; eliminating the duplicate does not impose a retention limit.
