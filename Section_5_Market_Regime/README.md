# Section 5 — Market Intelligence

Section 5 is the agreed home for separate analytical engines. The directory name
`Section_5_Market_Regime` remains unchanged for import compatibility. The current
`Market_Regime.py`, `regime_packet.py` and `features/` modules keep their existing
behaviour until a tested, explicit migration is approved.

The new design is in [contracts/BLUEPRINT.md](contracts/BLUEPRINT.md). Start there,
then read the [common contract](contracts/COMMON.md),
[shared feature audit](contracts/FEATURE_AUDIT.md) and
[implementation gates](contracts/IMPLEMENTATION.md).

**Status: Regime v1 and the partial Structure adapter run automatically.** The JSON
registry remains descriptive and is not imported by the runner. The existing
six-state calculations and all current consumers remain unchanged.

## First independent engine: Regime v1

[REGIME_V1.md](REGIME_V1.md) is the frozen experimental implementation spec.
`engines/regime.py` is pure and independent; Core owns `regime_inputs.py`,
`regime_research.py` and the shared analytical history store. Its research command remains available; automatic runner integration is described
below. It is not connected to chart or decision consumers. Structure now has a
conservative state adapter; the other eight engines remain design-only.

For a recent independently seeded research run:

```bash
python3 run_regime.py --symbols BTCUSDT ETHUSDT ENAUSDT --intervals 5m \
  --since 2026-10-01 --max-bars 1000 --summary --diagnostics
```

Repeat to resume. Omit `--since` to process from the available historical start.
The command uses at most the global budget, divided across the selected pairs,
with transactions capped at 200 candles. A quota can span several transactions.
Defaults come from active configured
symbols/timeframes; paused scopes are skipped. No downloads/restarts are started.
Pending Section 4 replay is reported explicitly and blocks the affected pair.

History is stored in `Section_1_Global_Core/memory_storage/Storage/intelligence.db`.
Different source/config/seed runs are retained with minimal immutable input
bundles and archived classifier/config source. Corrections outside the normal
feature-generation/policy-epoch pipeline require a new explicit `--revision`.
Do not label an old run current after out-of-band source edits. Historical results
are reconstructions with actual computation times, not proven live publications.

## Automatic runner integration

Regime and the [Structure state adapter](STRUCTURE_V1.md) now run through
`Section_1_Global_Core.analytical_processor` in the existing processor registry,
after features and decisions. One bounded shared turn visits active pair/engine
scopes round-robin (200 rows total, at most four visits, .20s soft time budget
checked between visits). There is no new downloader, daemon or unbounded loop.
Unavailable Section 4 inputs remain blocked; automatic processing also waits for
the latest closed-candle feature checkpoint so an old feature prefix is not
seeded as current analysis. Analytics never gate DI event progress.

For each source/config/pair, automatic processing saves a fixed seed from the
latest 32 committed closed candles, then resumes from its own checkpoint as new
candles close. The seed does not move each cycle. It is a recent classification
run, not a claim that every old candle has already been classified. Full historical
research runs and their earlier snapshots remain separate and preserved.

After pulling, use `python3 restart_runner.py`. No manual research command is
needed to keep these engines working. For inspection only:

```bash
python3 run_regime.py --automatic --symbols BTCUSDT --intervals 15m --summary --diagnostics
python3 run_regime.py --automatic --engine STRUCTURE --symbols BTCUSDT --intervals 15m --summary --diagnostics
```

The chart and BUY/SELL, confidence and opportunity consumers are unchanged.
Structure is intentionally PARTIAL until original confirmed-pivot event lineage
is available; it does not guess missing history or reuse candidate fields as facts.
