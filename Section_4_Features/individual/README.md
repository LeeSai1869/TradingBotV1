# Main feature files

Related calculations share one owning feature file. Liquidity, support/resistance,
sessions, order blocks/breakers, EMA and ADX/DI are consolidated. Independent
features and the six Section 5 modules retain their existing files.

`manifest.json` lists unique modules and ordered execution stages. Stages inside
one file can run at different points: EMA position depends on VWAP, for example.
The engine follows `steps`, never registry iteration or filesystem order.
Shared context, memory, checkpoints and field names are unchanged. No feature
recalculation is required solely for this regrouping. The combined gateway,
indicator displays, HUD fields, alerts and saved settings keep the same contract.

| Feature file | Pine source spans |
|---|---|
| [price.py](price.py) | 793–806 |
| [ema.py](ema.py) | 807–823, 824–872, 960–971, 5099–5104 |
| [wma.py](wma.py) | 873–878 |
| [vwap.py](vwap.py) | 879–959 |
| [rsi.py](rsi.py) | 972–976 |
| [adx.py](adx.py) | 977–978, 979–979, 980–984 |
| [momentum_weakening.py](momentum_weakening.py) | 985–987 |
| [momentum_divergence.py](momentum_divergence.py) | 988–993 |
| [atr.py](atr.py) | 994–1003 |
| [volume.py](volume.py) | 1004–1012 |
| [support_resistance.py](support_resistance.py) | 1013–1215, 1216–1631, 1632–1990, 1991–2406, 2407–2762 |
| [swing_pivots.py](swing_pivots.py) | 2763–2908 |
| [structure.py](structure.py) | 2909–3252 |
| [break_of_structure.py](break_of_structure.py) | 3253–3451 |
| [fair_value_gaps.py](fair_value_gaps.py) | 3452–3877 |
| [candle.py](candle.py) | 3878–3895 |
| [fractal_pivots.py](fractal_pivots.py) | 3896–3900 |
| [engulfing.py](engulfing.py) | 3910–3923 |
| [rejection.py](rejection.py) | 3924–3934 |
| [break_retest.py](break_retest.py) | 3935–3948 |
| [price_change.py](price_change.py) | 3949–3954 |
| [fibonacci.py](fibonacci.py) | 3955–4099 |
| [liquidity.py](liquidity.py) | 4100–4146, 4147–4162, 4163–4199, 4200–4208, 4209–4237, 4238–4245, 4246–4267, 4268–4283, 4284–4332, 4333–4365 |
| [order_blocks.py](order_blocks.py) | 4366–4610, 4611–4736 |
| [volume_profile.py](volume_profile.py) | 4737–4901 |
| [range.py](range.py) | 4902–4914 |
| [swing_levels.py](swing_levels.py) | 4915–4922 |
| [sessions.py](sessions.py) | 4923–4962, 4963–4984, 4985–5006, 5007–5028, 5037–5098 |
| [daily_levels.py](daily_levels.py) | 5105–5112 |
| [control.py](../../Section_5_Market_Regime/features/control.py) | 5741–5760 |
| [energy.py](../../Section_5_Market_Regime/features/energy.py) | 5761–5778 |
| [regime.py](../../Section_5_Market_Regime/features/regime.py) | 5779–5819 |
| [fatigue.py](../../Section_5_Market_Regime/features/fatigue.py) | 5820–5833 |
| [trend_state.py](../../Section_5_Market_Regime/features/trend_state.py) | 5834–5870 |
| [transition.py](../../Section_5_Market_Regime/features/transition.py) | 5871–5893 |
