# DI50 exit comparison — corrected 0.2% total costs

**Cost correction:** the user specifies 0.2% total round-trip costs. The prior v1 run used 4 bps fees +2 bps slippage per side (approximately 0.12% total); its cost assumptions are superseded for the current comparison. Original artifacts remain intact.

This run uses the user’s arithmetic exactly: **net return = gross chart-price return −0.2 percentage points**, deducted once per completed trade. No extra fees or slippage are stacked. Thus +0.5% gross gives +0.3% net, and +1% gross gives +0.8% net. This is a fixed cost allowance, not a claim that an exchange always charges this exact amount.

The standing maximum loss remains **0.5% net**, so the initial price stop is **0.3% below entry**. A 0.5% price stop would instead lose 0.7% net and is not substituted. Actual adverse opening gaps remain real losses. The tighter stop can change the winning trades and win rate; simply subtracting another 0.08% from old PnL is insufficient.

At +0.3% per win and −0.5% per loss, a 50% hit rate averages −0.1% per trade. Break-even is **62.5% wins**, before gap losses. At +0.8% per win it is **38.46%**.

Same 38 BTC and 11 SUI strict 15m DI entries and breakout gates; source hashes match. Reused only frozen prices/5m evidence, without live-memory reads, classifier recalculation or parameter fitting. The old regime-dependent policy is also rerun at corrected costs; it retains net +1% targets/activation, whereas new ordinary targets are gross.

Low-first and high-first are explicit OHLC order assumptions, not guaranteed tick-path bounds. Common execution fidelity is selected per entry across all policies. Full source periods and every losing trade remain in the saved results. No live strategy or workspace preset is enabled or changed.

## BTCUSDT — 38 entries

Execution frames: {'1m': 37, '5m': 1}.

| Policy | Wins low-first | Win% low / high | Mean net/trade low / high | PF low / high |
|---|---:|---:|---:|---:|
| old_regime_reference | 13/38 | 34.21% / 39.47% | +0.0789% / +0.1579% | 1.24 / 1.52 |
| fixed_1_net | 13/38 | 34.21% / 39.47% | +0.0132% / +0.0921% | 1.04 / 1.30 |
| fixed_1_gross | 14/38 | 36.84% / 39.47% | -0.0211% / +0.0132% | 0.93 / 1.04 |
| fixed_0_5_gross | 17/38 | 44.74% / 47.37% | -0.1421% / -0.1211% | 0.49 / 0.54 |
| trail_all | 14/38 | 36.84% / 39.47% | +0.0855% / +0.0338% | 1.27 / 1.11 |
| hybrid_0_5_entry_expansion | 17/38 | 44.74% / 47.37% | -0.0655% / -0.0509% | 0.76 / 0.81 |
| hybrid_1_entry_expansion | 14/38 | 36.84% / 39.47% | -0.0234% / +0.0043% | 0.93 / 1.01 |
| hybrid_0_5_micro_reclaim | 17/38 | 44.74% / 47.37% | -0.0342% / -0.0285% | 0.88 / 0.89 |
| hybrid_1_micro_reclaim | 14/38 | 36.84% / 39.47% | +0.0232% / +0.0357% | 1.07 / 1.12 |
| hybrid_0_5_volume_breakout | 17/38 | 44.74% / 47.37% | -0.0731% / -0.0520% | 0.74 / 0.80 |
| hybrid_1_volume_breakout | 14/38 | 36.84% / 39.47% | +0.0559% / +0.0837% | 1.18 / 1.28 |
| hybrid_0_5_volume_protected | 17/38 | 44.74% / 47.37% | -0.0731% / -0.0520% | 0.74 / 0.80 |

## SUIUSDT — 11 entries

Execution frames: {'1m': 10, '5m': 1}.

| Policy | Wins low-first | Win% low / high | Mean net/trade low / high | PF low / high |
|---|---:|---:|---:|---:|
| old_regime_reference | 4/11 | 36.36% / 36.36% | +0.1470% / +0.1470% | 1.46 / 1.46 |
| fixed_1_net | 4/11 | 36.36% / 36.36% | +0.0455% / +0.0455% | 1.14 / 1.14 |
| fixed_1_gross | 4/11 | 36.36% / 36.36% | -0.0273% / -0.0273% | 0.91 / 0.91 |
| fixed_0_5_gross | 5/11 | 45.45% / 54.55% | -0.1364% / -0.0636% | 0.50 / 0.72 |
| trail_all | 4/11 | 36.36% / 36.36% | +0.1309% / -0.0112% | 1.41 / 0.96 |
| hybrid_0_5_entry_expansion | 5/11 | 45.45% / 54.55% | -0.1364% / -0.0636% | 0.50 / 0.72 |
| hybrid_1_entry_expansion | 4/11 | 36.36% / 36.36% | -0.0273% / -0.0273% | 0.91 / 0.91 |
| hybrid_0_5_micro_reclaim | 5/11 | 45.45% / 54.55% | -0.0249% / +0.0479% | 0.91 / 1.21 |
| hybrid_1_micro_reclaim | 4/11 | 36.36% / 36.36% | +0.0633% / +0.0048% | 1.20 / 1.02 |
| hybrid_0_5_volume_breakout | 5/11 | 45.45% / 54.55% | -0.1364% / -0.0636% | 0.50 / 0.72 |
| hybrid_1_volume_breakout | 4/11 | 36.36% / 36.36% | -0.0273% / -0.0273% | 0.91 / 0.91 |
| hybrid_0_5_volume_protected | 5/11 | 45.45% / 54.55% | -0.1364% / -0.0636% | 0.50 / 0.72 |

## Evidence

`protocol.json` defines the correction; `summary.json` contains every policy/path summary; `*_results.json.gz` retains all trades; `all_exit_trades.csv` lists every exit. `execution_audit.json` checks all 1,176 trades for gross/net arithmetic, raw initial stops, target basis, price-bar fills and causal gate timestamps: zero mismatches. 36 targeted tests passed, including the cost arithmetic, hard stops, trailing and breakeven protection.

Reproduce: `PYTHONPATH=/tmp/btc-section5-test-deps:. .venv-build/bin/python3 -m research_reports.DI50_breakout_exit_routing_cost20bps.study`
