# Numbered Section 4 feature calculations

This is the only active Section 4 calculation folder. Each numbered `4.2.x`
section in `sections_4&5_Tradingview` owns one file. There is no 4.2.15 in that
source; no section is invented to fill the gap.

Engulfing, rejection, candle pivots and break/retest stay together in 4.2.12.
Swing-pivot confirmation and BOS stay in 4.2.10. Range location and swing location
remain separate because the source numbers them 4.2.19 and 4.2.20.
RSI and ADX/DI are calculated by 4.2.6 momentum, with their UI identities retained.
EMA belongs to 4.2.2 trend; EMA structure and WMA are under 4.2.3 in the source.

`registry.py` exposes these modules and output fields. `../execution/` contains
shared state, arithmetic, the composition engine and checkpoint support, not a
second set of formulas. `../conversion/manifest.json` records source-line ownership,
field types and dependency order. The runtime does not parse Pine or run a converter.
The runner, permanent memory, forming-candle preview, HUD, alerts and chart readers
all use these same calculations/field names. Old feature implementations and the
superseded `individual` tree have been removed; previous source backups remain.

| Section | File | Pine lines |
|---|---|---|
| 4.2.1 PRICE | [price.py](price.py) | 793–806 |
| 4.2.2 TREND | [trend.py](trend.py) | 807–823 |
| 4.2.3 EMA STRUCTURE | [ema_structure.py](ema_structure.py) | 824–878 |
| 4.2.4 VWAP | [vwap.py](vwap.py) | 879–959 |
| 4.2.5 PRICE LOCATION | [price_location.py](price_location.py) | 960–971 |
| 4.2.6 MOMENTUM | [momentum.py](momentum.py) | 972–993 |
| 4.2.7 VOLATILITY | [volatility.py](volatility.py) | 994–1003 |
| 4.2.8 VOLUME DATA | [volume.py](volume.py) | 1004–1012 |
| 4.2.9 SUPPORT AND RESISTANCE | [support_resistance.py](support_resistance.py) | 1013–2762 |
| 4.2.10 MARKET STRUCTURE | [market_structure.py](market_structure.py) | 2763–3451 |
| 4.2.11 FAIR VALUE GAP | [fair_value_gaps.py](fair_value_gaps.py) | 3452–3877 |
| 4.2.12 CANDLE FEATURES | [candle.py](candle.py) | 3878–3949 |
| 4.2.13 PRICE CHANGE DATA | [price_change.py](price_change.py) | 3950–3955 |
| 4.2.14 FIBONACCI STRUCTURE ENGINE | [fibonacci.py](fibonacci.py) | 3956–4099 |
| 4.2.16 LIQUIDITY DETECTION | [liquidity.py](liquidity.py) | 4100–4365 |
| 4.2.17 ORDER BLOCK DETECTION | [order_blocks.py](order_blocks.py) | 4366–4736 |
| 4.2.18 VOLUME PROFILE SETTINGS | [volume_profile.py](volume_profile.py) | 4737–4901 |
| 4.2.19 RANGE LOCATION | [range.py](range.py) | 4902–4914 |
| 4.2.20 SWING LOCATION | [swing_location.py](swing_location.py) | 4915–4922 |
| 4.2.21 SESSION CONTEXT | [sessions.py](sessions.py) | 4923–5098 |
| 4.2.22 PRICE EXTENSION | [price_extension.py](price_extension.py) | 5099–5104 |
| 4.2.23 DAILY REFERENCE LEVELS | [daily_levels.py](daily_levels.py) | 5105–5112 |
