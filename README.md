# Scalp Indicator

The application calculates Section 4 market features, derives Section 5 analytical
context, and produces decisions and chart data. See the
[Global Core README](Section_1_Global_Core/GLOBAL_CORE_README.md),
[feature calculations](Section_4_Features/features/README.md), and
[Section 5 README](Section_5_Market_Regime/README.md).

## Storage policy

Calculation and permanent retention are separate decisions. A calculation may run
as part of an engine without its intermediate output being saved for every candle.
The complete policy and field-retirement requirements are in
[STORAGE_POLICY.md](STORAGE_POLICY.md).

- `klines.db` retains the canonical raw candles.
- `features.db` retains explicitly justified shared historical measurements,
  event lineage, and the checkpoints needed for correct continuation/replay.
- `ADCN.db` retains analytical results, decisions, their necessary evidence and
  checkpoints. Section 5 uses this database after the verified consolidation.
- Aliases must resolve to a canonical value rather than acquire another permanent
  value per candle. Existing readers must be migrated before physical removal.
- Optional, inexpensive derivatives belong in their consuming calculator, with
  bounded caching where necessary. Expensive, repeatedly consumed historical
  measurements can justify retention after measurement of their actual cost.

The initial scope is duplicate feature aliases. Other fields require individual
review; absence of a named reference is not authorization for bulk deletion.
