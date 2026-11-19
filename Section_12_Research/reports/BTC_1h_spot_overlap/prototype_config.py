"""Fixed causal spot BUY/SELL hypotheses; no optimization or production writes.

Price/EMA contexts are explicit proxies, not replacements for Section 5 outputs.
Use the existing analyzer for alternating next-open spot fills and cost modeling.
"""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))

import json
from pathlib import Path


def leaf(field, op, value=None, *, other=None, lag=0, other_lag=0):
    item = dict(field=field, op=op)
    if other is None:
        item['value'] = value
    else:
        item['other_field'] = other
        if other_lag:
            item['other_lag'] = other_lag
    if lag:
        item['lag'] = lag
    return item


def all_of(*values):
    return dict(all=list(values))


def any_of(*values):
    return dict(any=list(values))


def recent(field, op, value, lags):
    return any_of(*(leaf(field, op, value, lag=lag) for lag in lags))


def configuration():
    up = all_of(leaf('price.close', 'gte', other='feature.ema50', lag=1, other_lag=1),
                leaf('feature.ema50_slope_atr', 'gt', 0, lag=1))
    down = all_of(leaf('price.close', 'lt', other='feature.ema50', lag=1, other_lag=1),
                  leaf('feature.ema50_slope_atr', 'lt', 0, lag=1))
    price_reclaim = leaf('price.close', 'gt', other='price.high', other_lag=1)
    activity = leaf('feature.relative_volume', 'gte', 1)
    pressure = recent('event.di_minus_peak', 'eq', True, (0, 1, 2))
    rsi_rising = leaf('feature.rsi', 'gt', other='feature.rsi', other_lag=1)
    plus_rising = leaf('di.di_plus', 'gt', other='di.di_plus', other_lag=1)
    return dict(
        version='btc-hour-strategy-analyzer-v1', id='spot_overlap_hypothesis_v1',
        description=('Unoptimized causal prototype: prior EMA context; activity; independent pressure/price response. '
                     'No future native pivots or Section 5 fallback. No protective stops, fixed targets or time exits; research only.'),
        execution=dict(fee_bps_per_side=10, slippage_bps_per_side=2, initial_capital=100),
        branches=[
            dict(id='buy_up_pullback_proxy', side='BUY', when=all_of(
                up, recent('feature.rsi', 'lte', 60, (1, 2, 3)), activity, price_reclaim,
                any_of(pressure, all_of(leaf('di.dominant', 'eq', 'PLUS'), plus_rising, rsi_rising)))),
            dict(id='buy_down_reversal_proxy', side='BUY', when=all_of(
                down, recent('feature.rsi', 'lte', 40, (1, 2, 3)), activity, price_reclaim, pressure)),
            dict(id='buy_mixed_recovery_proxy', side='BUY', when=all_of(
                {'not': any_of(up, down)}, recent('feature.rsi', 'lte', 50, (1, 2, 3)),
                activity, price_reclaim, plus_rising, rsi_rising)),
            dict(id='sell_price_and_control_loss', side='SELL', when=all_of(
                leaf('price.close', 'lt', other='price.low', other_lag=1),
                leaf('di.di_plus', 'lt', other='di.di_plus', other_lag=1))),
            dict(id='sell_ema50_loss', side='SELL', when=all_of(
                leaf('price.close', 'lt', other='feature.ema50'),
                leaf('price.close', 'gte', other='feature.ema50', lag=1, other_lag=1))),
            dict(id='sell_exhaustion_with_price_weakness', side='SELL', when=all_of(
                recent('feature.rsi', 'gte', 70, (1, 2)),
                recent('event.di_plus_peak', 'eq', True, (0, 1)),
                leaf('price.close', 'lt', other='price.close', other_lag=1))),
        ])


def main():
    output = Path(__file__).resolve().parent
    config = configuration()
    baseline = json.loads((output.parents[2] / 'Section_12_Research/reports/BTC_1h_sequences/strategy_configs/di_baseline_v1.json').read_text())
    baseline.update(id='di_baseline_same_costs', execution=config['execution'])
    for name, value in [('spot_overlap_hypothesis_v1.json', config), ('di_baseline_same_costs.json', baseline)]:
        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
        print(output / name)


if __name__ == '__main__':
    main()
