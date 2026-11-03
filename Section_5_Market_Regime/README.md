# Section 5 — Market Intelligence

Section 5 is the agreed home for separate analytical engines. The directory name
`Section_5_Market_Regime` remains unchanged for import compatibility. The current
`Market_Regime.py`, `regime_packet.py` and `features/` modules keep their existing
behaviour until a tested, explicit migration is approved.

The new design is in [contracts/BLUEPRINT.md](contracts/BLUEPRINT.md). Start there,
then read the [common contract](contracts/COMMON.md),
[shared feature audit](contracts/FEATURE_AUDIT.md) and
[implementation gates](contracts/IMPLEMENTATION.md).

**Status: contract/design release 1.0.0; not new runtime engines.** The JSON
registry is descriptive and is not imported by the runner. This documentation
adds no calculations, database migrations, replays, strategy changes or UI options.
