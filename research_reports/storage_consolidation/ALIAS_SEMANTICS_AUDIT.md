# Feature alias semantic audit

Scope: `features.db` only. No schema, data, calculations or running services were changed.

## Findings

**24 mappings are exact copies in the current formula-v3 output path. Two mappings have no source output and are not demonstrated duplicates.** The mapping loop copies the same source value without arithmetic, history offsets, unit conversion or another lookup. Corresponding declared types match. No later `Engine.step` extra export overwrites these source/alias fields. A distinct-value/type construction check passed for all 24 mappings.

Stored-history sampling inspected **1726 distinct rows**: formula 1: 386, formula 2: 49, formula 3: 1291. This is not a full database equality scan.

No unequal non-NULL value pairs were found in this sample. Every current-v3 pair was equal or both NULL. Older rows contain alias-only data, so removing columns without a verified transfer could lose history.

| Alias | Canonical field | Current classification | Historical sample |
|---|---|---|---|
| `ema_gap_7_25` | `ema_gap7_25` | Exact copy; matching declared type | 49 alias-only older rows; preserve/backfill before removal |
| `ema_gap_25_50` | `ema_gap25_50` | Exact copy; matching declared type | 49 alias-only older rows; preserve/backfill before removal |
| `ema_gap_50_100` | `ema_gap50_100` | Exact copy; matching declared type | 49 alias-only older rows; preserve/backfill before removal |
| `ema_gap_7_25_pct` | `ema_gap7_25_pct` | Exact copy; matching declared type | 49 alias-only older rows; preserve/backfill before removal |
| `ema_gap_25_50_pct` | `ema_gap25_50_pct` | Exact copy; matching declared type | 49 alias-only older rows; preserve/backfill before removal |
| `ema_gap_50_100_pct` | `ema_gap50_100_pct` | Exact copy; matching declared type | 49 alias-only older rows; preserve/backfill before removal |
| `distance_to_poc_atr` | `distance_to_pocatr` | Exact copy; matching declared type | No unequal populated pair found |
| `prev_close` | `c1` | Exact copy; matching declared type | 289 alias-only older rows; preserve/backfill before removal |
| `newyork_high` | `new_york_high` | Exact copy; matching declared type | 57 alias-only older rows; preserve/backfill before removal |
| `newyork_low` | `new_york_low` | Exact copy; matching declared type | 57 alias-only older rows; preserve/backfill before removal |
| `vp_vah` | `vp_va_high` | Exact copy; matching declared type | No unequal populated pair found |
| `vp_val` | `vp_va_low` | Exact copy; matching declared type | No unequal populated pair found |
| `nearest_support_price` | `nearest_support` | Exact copy; matching declared type | No unequal populated pair found |
| `nearest_resistance_price` | `nearest_resistance` | Exact copy; matching declared type | No unequal populated pair found |
| `swing_candidate_pivot` | `candidate_pivot` | Exact copy; matching declared type | No unequal populated pair found |
| `swing_candidate_high_price` | `candidate_pivot_high_price` | Exact copy; matching declared type | No unequal populated pair found |
| `swing_candidate_low_price` | `candidate_pivot_low_price` | Exact copy; matching declared type | No unequal populated pair found |
| `swing_pivot_high_confirmed` | `pivot_high_confirmed_this_bar` | Missing canonical output; unresolved legacy field | All sampled values NULL; not proof of all historical rows |
| `swing_pivot_low_confirmed` | `pivot_low_confirmed_this_bar` | Missing canonical output; unresolved legacy field | All sampled values NULL; not proof of all historical rows |
| `swing_direction` | `current_swing_direction` | Exact copy; matching declared type | No unequal populated pair found |
| `swing_latest_confirmed_high` | `latest_confirmed_pivot_high` | Exact copy; matching declared type | No unequal populated pair found |
| `swing_latest_confirmed_low` | `latest_confirmed_pivot_low` | Exact copy; matching declared type | No unequal populated pair found |
| `swing_nearest_high` | `nearest_swing_high` | Exact copy; matching declared type | No unequal populated pair found |
| `swing_nearest_low` | `nearest_swing_low` | Exact copy; matching declared type | No unequal populated pair found |
| `swing_distance_to_high_pct` | `distance_to_swing_high_pct` | Exact copy; matching declared type | No unequal populated pair found |
| `swing_distance_to_low_pct` | `distance_to_swing_low_pct` | Exact copy; matching declared type | No unequal populated pair found |

## Semantic boundaries

- `prev_close` maps to `c1`, the previous candle close; it is not the current close. Older rows may retain only `prev_close`.
- The New York fields are alternate spellings of the same session extremes, not prior-session extremes.
- `vp_vah`/`vp_val` copy the value-area high/low; they are not POC or high/low-volume nodes.
- `nearest_support_price`/`nearest_resistance_price` copy the selected nearest support/resistance price. Zone bounds, IDs and institutional levels remain distinct fields.
- Swing candidate values remain developing pivots. Latest confirmed pivots, nearest swings, and confirmation events are different concepts and must not be collapsed into one another. Each valid alias maps only to its explicitly paired canonical field.
- `swing_pivot_high_confirmed` and `swing_pivot_low_confirmed` reference absent `pivot_high_confirmed_this_bar` / `pivot_low_confirmed_this_bar` fields. Do not substitute a candidate flag, direction flag or structure event merely because its name sounds similar.

## Retirement decision

The 24 mappings support removing duplicate *future storage*, after reader adaptation. This audit does not authorize dropping historical columns wholesale. Backfill canonical NULLs from legacy values, reject conflicting non-NULL pairs, validate the complete migrated ranges, and preserve historical formula versions. Resolve the two orphan fields separately.

Evidence: `Section_4_Features/execution/contract.py`, `Section_4_Features/execution/engine.py`, the live read-only schema and `alias_semantics_audit.json`.
