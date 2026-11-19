"""Shared input-field catalog for the app and the offline research workspace."""
import re
from . import strategy_analyzer as analyzer
from .pivot_candle_source import unpack


def field_catalog(source):
    source = unpack(source)
    rows = source.get('candles', [])
    legacy = source.get('version') == 'btc-hour-sequence-source-v1' and source.get('symbol') == 'BTCUSDT' and source.get('timeframe') == '1h'
    general = source.get('version') in ('pivot-candle-source-v1','memory-candle-source-v1') and re.fullmatch(r'[A-Z0-9]{2,30}USDT', source.get('symbol', '')) and source.get('timeframe') in analyzer.FRAMES
    if not ((legacy or general) and rows):
        raise ValueError('Choose a nonempty spot candle row-source export, not an analysis or pivot report')
    sample = rows if len(rows) <= 2000 else rows[:1000] + rows[-1000:]
    fields = []

    def add(name, values, **extra):
        good = [v for v in values if (type(v) in (str, bool) or analyzer.number(v)) and v not in ('UNKNOWN', 'UNAVAILABLE')]
        kind = 'number' if good and all(analyzer.number(v) for v in good) else 'boolean' if good and all(type(v) is bool for v in good) else 'string'
        options = list(dict.fromkeys(v for v in good if isinstance(v, (str, bool)) and len(str(v)) <= 80))
        fields.append(dict(id=name, kind=kind, options=options[:30], sample_present=len(good), sample_total=len(values), **extra))

    names = sorted(set(source.get('exported_feature_columns', [])) | {key for row in rows for key in row.get('features', {})})
    for name in names:
        add('feature.' + name, [r['features'].get(name) for r in sample if r.get('feature_valid') and not r['features'].get('measurement_gap')], group='Stored features')
    for name in ('open', 'high', 'low', 'close', 'volume'):
        add('price.' + name, [r.get(name) for r in sample], group='Candle prices')
    for name in sorted(analyzer.DI_FIELDS):
        add('di.' + name, ['PLUS', 'MINUS', 'BALANCED'] if name == 'dominant' else [0.], group='DI measurements')
    for name in sorted(analyzer.EVENT_FIELDS):
        add('event.' + name, [True, False], group='DI events')
    histories = source.get('engine_history', {})
    context_rows = {key: len(value.get('results', {})) for key, value in histories.items()}
    for frame in dict.fromkeys((source['timeframe'], '1h', '4h', '1d', *[key.split(':')[0] for key in histories])):
        for engine in ('REGIME', 'TREND', 'STRUCTURE', 'MOMENTUM', 'VOLATILITY', 'PARTICIPATION', 'PHASE', 'LIQUIDITY', 'SENTIMENT', 'BIAS'):
            history = histories.get(frame + ':' + engine, {})
            results = list(history.get('results', {}).values())
            if frame == source['timeframe']:
                inline = [r['context'][engine] for r in sample if engine in r.get('context', {})]
                results.extend(inline)
                if inline:
                    context_rows[frame + ':' + engine] = sum(engine in r.get('context', {}) for r in rows)
            values = {}
            for payload in results[:100] + results[-100:]:
                def walk(value, prefix=''):
                    for key, item in value.items():
                        name = prefix + key
                        if isinstance(item, dict):
                            walk(item, name + '.')
                        elif item is None or type(item) in (str, bool) or analyzer.number(item):
                            values.setdefault(name, []).append(item)
                walk(payload.get('classification') or {})
            for name in ({'primary', 'direction'} if engine == 'REGIME' else {'direction', 'strength_band'} if engine == 'TREND' else set()):
                values.setdefault(name, [])
            for name, samples in sorted(values.items()):
                add(f'context.{frame}.{engine}.{name}', samples, group=frame + ' ' + engine.title(), history_rows=len(history.get('results', {})))
    return dict(symbol=source['symbol'], timeframe=source['timeframe'], candles=len(rows), source_id=source['source_id'],
                risk_budget_pct=.5 if general else None,
                first=rows[0]['open_time'], last=rows[-1]['close_time'] + 1, fields=fields,
                feature_columns=len(names), context_rows=context_rows,
                note='Field choices come from this input. Sample availability uses up to 2,000 candles; replay diagnostics give exact unknown counts. Context is exact last-closed historical context, not today’s classification.')

