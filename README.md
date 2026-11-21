# Scalp Indicator

The application calculates Section 4 market features, derives Section 5 analytical
context, and produces decisions and chart data. See the
[Global Core README](Section_1_Global_Core/GLOBAL_CORE_README.md),
[feature calculations](Section_4_Features/features/README.md), and
[Section 5 README](Section_5_Market_Regime/README.md).

## Repository layout

| Folder | Contents |
|---|---|
| Sections 1–11 | Application engines, contracts, storage and chart UI |
| [Section_12_Research](Section_12_Research/README.md) | Studies, reports, research UI and exports |
| [Section_13_Development](Section_13_Development/README.md) | Tests, diagnostics, profiling and archives |
| [Section_14_Operations](Section_14_Operations/README.md) | Service, account, configuration and storage tools |
| [Section_15_Execution_Bot](Section_15_Execution_Bot/README.md) | Independent Spot paper worker and execution ledger; real orders disabled |
| [docs](docs/) | Setup, storage and operational documentation |
| `packaging/` | Standalone builds, dependencies and vendor assets |
| `mobile/` | Mobile application source |

`portable_app.py` remains the standalone entry point. Git configuration and build
workflow files stay at the root where their tools expect them. Market data and
private configuration paths are unchanged.

After pulling, use the [local artifact organizer](Section_14_Operations/README.md#local-files-left-after-pulling)
to preview and archive ignored reports or backups left in the old folders.

## Storage policy

Calculation and permanent retention are separate decisions. A calculation may run
as part of an engine without its intermediate output being saved for every candle.
The complete policy and field-retirement requirements are in
[docs/STORAGE_POLICY.md](docs/STORAGE_POLICY.md).

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
