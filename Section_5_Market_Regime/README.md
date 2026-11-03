# Section 5 — Market Intelligence

Section 5 is the agreed home for separate analytical engines. The directory name
`Section_5_Market_Regime` remains unchanged for import compatibility. The current
`Market_Regime.py`, `regime_packet.py` and `features/` modules keep their existing
behaviour until a tested, explicit migration is approved.

The new design is in [contracts/BLUEPRINT.md](contracts/BLUEPRINT.md). Start there,
then read the [common contract](contracts/COMMON.md),
[shared feature audit](contracts/FEATURE_AUDIT.md) and
[implementation gates](contracts/IMPLEMENTATION.md).

**Status: Regime v1 is available as an on-demand shadow engine.** The JSON
registry remains descriptive and is not imported by the runner. The existing
six-state calculations and all current consumers remain unchanged.

## First independent engine: Regime v1

[REGIME_V1.md](REGIME_V1.md) is the frozen experimental implementation spec.
`engines/regime.py` is pure and independent; Core owns `regime_inputs.py`,
`regime_research.py` and the shared analytical history store. It is an on-demand
shadow engine, not connected to the live scheduler, chart or decision consumers.
The other nine engine contracts remain design-only.

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
