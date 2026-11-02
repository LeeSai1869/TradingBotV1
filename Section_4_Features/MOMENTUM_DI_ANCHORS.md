# Momentum DI anchors (feature-only)

The addition belongs to the existing **Momentum** owner. `momentum.update` detects
confirmed DI+/DI-/signed-spread turns; `momentum_anchors.update` attaches the
already-calculated price structure and same-timeframe regime at the end of the
feature pass. No decision, confidence, opportunity, UI or execution rule changes.
No SELL override or order placement is implemented.

The 112 new typed exports include six confirmed high/low levels and their origin
bar/time, confirmation availability, qualification, age, delta from anchor and
running range; candidate values/phase; price-high/low anchors with origin and
known times; DI at price origin (when retained) versus DI at confirmation;
confirmation-anchored deltas/ranges; frozen ATR retest tolerance, observed
close-break/retest flags; and sparse JSON confirmation/context events.

`di_signed_spread = di_plus - di_minus`. The existing absolute `di_spread` and all
existing DI/ADX calculations remain untouched. Features are per symbol/timeframe.

## Detector and qualification

- Startup tracks both sides, allowing either first high or first low to confirm.
- Phases are `SEEK_TURN`, `SEEK_HIGH`, `SEEK_LOW`. Confirmation requires a strict
  reversal, the configured DI-point magnitude, origin delay and confirmation gap.
- Equal plateaus retain their earliest origin. Opposite extremes between origin
  and delayed confirmation are retained using bounded source history.
- Track the actual extreme regardless of its qualification range. After geometric
  confirmation, apply inclusive min/max ranges independently for each channel/side.
  A 45 peak is stored as 45 even when the allowed maximum is 40; it is unqualified,
  not changed into a lower peak or allowed to block the next low.
- Each confirmed cycle appends. Last confirmed high/low values and origin times
  are never replaced by a later cycle. Classification is HH/LH/EH or LL/HL/EL
  relative to the preceding confirmed same-side extreme. Rolling min/max fields
  belong to the latest anchor, separately from immutable confirmation events.
- Tracking is closed-candle only and idempotent for the same timestamp. Missing DI
  or a candle gap starts a new segment instead of asserting continuous extrema.
  Histories are bounded. No earlier row is backdated or rewritten at confirmation.

## Price and regime links

Price inputs come from existing `nearestSwingHigh/Low`, bars and times after the
structure feature has run. A price anchor is first usable when observed as known,
not at its older origin timestamp. Original source time, known time and current
regime/structure are preserved. Momentum at price origin is unknown if the bounded
history does not contain that candle; confirmation momentum is stored separately.

Each DI confirmation links to both price anchors already known at that close and
records origin-bar lags. There is no forced one-to-one matching or future-pivot
search. Later price pivots cannot modify an earlier stored DI event. Regime at DI
origin and at confirmation are separate event fields.

`*_confirmed_age` counts from DI confirmation. `*_since_min/max` and price-anchor
running ranges start at confirmation/known availability, not retrospectively at
origin. `*_delta` compares the current channel with the actual confirmed DI peak;
`*_from_price_high/low` compares it with DI at price-anchor confirmation.

Retest flags require an anchor age, an extreme within +/- the frozen tolerance,
and a close away from the level. Close-break flags identify a confirmed close
beyond tolerance. They are observations, **not** trade entry/exit instructions.
An intrabar protective exit belongs to a future position-risk/execution component.

## Configuration

Edit `Section_2_Inputs/Inputs.py` → `MOMENTUM_DI_ANCHORS`; omitted keys use defaults
from `features/momentum_anchors.py`. `Engine(..., parameters={...})` also accepts
these keys for isolated research. Invalid ranges fail explicitly.

| Key | Default | Meaning |
| --- | ---: | --- |
| `diAnchorReversal` | 2.0 | DI-point reversal magnitude; strict direction still required at zero |
| `diAnchorConfirmBars` | 1 | Minimum bars from extreme to confirmation |
| `diAnchorConfirmSpacing` | 1 | Minimum bars between confirmations (not between origin candles) |
| `diAnchorHistory` | 32 | Retained confirmations per channel and side, maximum 128 |
| `diAnchorSourceHistory` | 256 | Origin lookup/seed history, maximum 512; must exceed both delays |
| `diAnchorRetestATR` | 0.1 | Frozen price-anchor ATR tolerance |
| `diAnchorRetestAge` | 1 | Bars after a price reference becomes known before a retest flag |

For `Plus` and `Minus`, `diAnchor{channel}HighMin/HighMax` default to 30/100 and
`LowMin/LowMax` to 0/30. For `Spread`, defaults are high 0/100, low -100/0. All are
inclusive and independently configurable. The 30 default is an initial research
setting, not a finding that it outperforms 35 or 40. Qualification never changes
geometric detection. A settings change repairs only this component's columns;
changing detector parameters can change its historical extrema and events.

## Storage and isolated replay

Exports are registered under Momentum and automatically migrate into existing
feature memory. Sparse `di_anchor_events` is `[]` on ordinary candles; full bounded
histories live in the versioned feature checkpoint, not repeated on every row.
The addition's selective repair hydrates existing DI, price-swing and regime
columns rather than recalculating those producers. Its new internal state is
checkpointed/merged through the existing replay mechanism.

The pre-change calculation fingerprints were independently compared with this
commit's additions: **no existing formula fingerprint changed**. The repair plan
contains exactly the 112 new columns. Legacy packet checksum tests still verify
all prior outputs after excluding only the added fields. No broad memory deletion,
formula-version reset or full feature replay is required. Paused pairs obey the
existing policy. Restart the runner; logs should show targeted new-field replay.

## Corrected Pine Script

- `pine/momentum_di_anchors.pine`: complete Pine v6 standalone diagnostic. It
  computes its own DI/ATR series. Price/regime adapters default to unavailable;
  an explicitly enabled **demo** confirmed-price-pivot mode is separate from the
  existing structure engine. It never labels demo pivots as production structure.
- `pine/momentum_di_anchors_integration.pine`: no indicator declaration, DI/ATR
  recalculation, plots, orders or overrides. Replace the old repeated peak blocks;
  it reads aliases for existing DI, ATR, confirmed structure and regime fields.
  Its `da*` names avoid the duplicated `diSpreadSeries` declaration. Type/helper
  definitions must be at global Pine v6 scope. If using the supplied
  `f_market_state` function, expose values through the existing MarketFeatures /
  MarketRegime handoff and map the aliases there; do not paste UDT definitions
  inside that function or reference its locals from global scope.

Both versions preserve actual extrema, qualify afterward, append immutable cycles,
use closed confirmation times (`time_close`, equivalent to Python close_time+1),
retain bounded histories, handle signed negative spread and reset after gaps.
The standalone raw DI plots can move intrabar; confirmed anchors do not. All price
retest/break features update only on confirmed candles. Pine v6 uses float
1/0/na for unavailable boolean diagnostics because its bool cannot be na.

Python causal vectors, restart/partial replay and legacy equivalence are tested.
The TradingView compiler is not available in this workspace, so Pine compilation
and live TradingView execution still require validation in its editor. This is
not a claim of measured strategy performance or cross-feed DI parity.
