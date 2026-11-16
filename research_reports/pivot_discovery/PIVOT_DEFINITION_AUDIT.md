# What the study's pivot labels mean

This audit inspected the original `sections_4&5_Tradingview` Pine source,
the current Python `market_structure.update`, the event exporter, the study
reader and every frozen BTC/SUI 15m native pivot event. No pivot definition,
production function or stored measurement was changed.

## Existing state machine

- `candidatePivot = +1`: track a candidate high. A strictly higher high moves
  the candidate's price and origin to the new candle.
- `candidatePivot = -1`: track a candidate low. A strictly lower low moves
  the candidate's price and origin to the new candle.
- Before any confirmed opposite pivot exists, initialization uses the stored
  bootstrap opposite extreme.
- With candidate high H and previous confirmed low L, a later closed candle
  confirms H when `close <= H - 0.25 * (H - L)`.
- With candidate low L and previous confirmed high H, a later closed candle
  confirms L when `close >= L + 0.25 * (H - L)`.
- Confirming H immediately switches to the low candidate and seeds it with
  the low of the candle which confirmed H. Confirming L performs the reverse.
- The new candidate cannot confirm on its own origin candle. The next candle
  can confirm it. It need not first break the preceding same-side confirmed
  pivot: a higher low or lower high is possible.

Both candidate price fields can remain populated, but the selector makes only
one side active. There is no minimum percentage swing, ATR threshold or
multi-candle origin spacing in this base swing detector. The study's 1%
threshold labels subsequent outcomes; it does not define pivot confirmation.

Original Pine source: lines 2785–2885. Python counterpart:
`Section_4_Features/features/market_structure.py`, lines 59–231.
The event exporter observes the existing confirmation branches; it does not
find additional pivots. The research reader imports those events.

## Why adjacent arrows appear

BTC on 14 November 2026, Pakistan time:

| Side | Origin candle opens | Extreme | Confirmed at close |
|---|---|---:|---|
| Low | 13:45 | 66,966.79 | 14:15 |
| High | 14:00 | 67,262.01 | 14:30 |
| Low | 14:15 | 67,034.79 | 14:45 |

At the 14:30 close the high is confirmed. The low of that same 14:15–14:30
candle becomes the new low candidate. At 14:45 that low confirms. Drawing
both at their historical origin candles places arrows on adjacent candles.
They were not both confirmed at 14:15, nor confirmed simultaneously.

A rule requiring the next candidate's origin to be at or after the preceding
pivot's confirmation **close** would reject this same-candle seeding. The
current Pine/Python rules permit an origin on the preceding confirmation
candle, starting at that candle's **open**.

## Full frozen-cohort checks

| Check | BTC 15m | SUI 15m |
|---|---:|---:|
| Events inspected | 103,330 | 37,126 |
| Adjacent opposite origin pairs | 31,622 | 10,690 |
| Two events confirmed at the same close | 0 | 0 |
| Consecutive same-type confirmations | 0 | 0 |
| Next origin before previous confirmation candle | 0 | 0 |
| Origin extreme matches stored candle | 103,330 / 103,330 | 37,126 / 37,126 |
| Confirmation occurs on a later candle | 103,330 / 103,330 | 37,126 / 37,126 |
| 25% confirmation threshold satisfied | 103,329 / 103,329 | 37,125 / 37,125 |
| Tracked extreme from prior opposite confirmation matches | 103,329 / 103,329 | 37,125 / 37,125 |

The first event in each instrument is excluded from checks requiring a prior
confirmed opposite pivot, because it uses the bootstrap reference. Full
machine-readable counts and recent examples are in `pivot_sequence_audit.json`.
Three existing runtime tests also passed: initial confirmations, causal event
lineage/restart parity, and candidates/counters not manufacturing events.

## Separate structural qualification

After emitting a base swing confirmation, the same function has additional
structure-specific checks. In a bullish structure valid types are HH/HL;
in a bearish structure LH/LL; in a ranging structure EH/EL. Further lifecycle
conditions govern additions to the structure pivot arrays.

The current study does not require a base swing event to pass all those later
structure qualifications. Its reference counts and prior descriptive results
therefore refer to base confirmed swings, not exclusively structure-qualified
or protected pivots. This distinction must remain explicit before selecting
the strategy's intended reference set.
