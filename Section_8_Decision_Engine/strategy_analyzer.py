"""Offline candle-rule research. Never imports or publishes live decision state."""
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import math

from . import pivot_sequences

VERSION = 'btc-hour-strategy-analyzer-v1'
STEP = 3600000
UNKNOWN = None
OPS = {'eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'available', 'missing'}
DI_FIELDS = {'di_plus', 'di_minus', 'abs_spread', 'signed_spread', 'dominance', 'dominant', 'adx'}
EVENT_FIELDS = {'di_minus_peak', 'di_plus_peak', 'spread_peak', 'di_only_buy_turn', 'di_only_sell_turn'}
EXECUTION = dict(fee_bps_per_side=4., slippage_bps_per_side=2., initial_capital=100.)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_config(config):
    if not isinstance(config, dict) or config.get('version') != VERSION:
        raise ValueError('Use config version ' + VERSION)
    if set(config) - {'version', 'id', 'description', 'branches', 'execution'}:
        raise ValueError('Unknown configuration keys')
    if not isinstance(config.get('id'), str) or not config['id']:
        raise ValueError('A strategy id is required')
    branches = config.get('branches')
    if not isinstance(branches, list) or not branches:
        raise ValueError('Provide BUY and SELL branches')
    ids = set()

    def expression(node, depth=0):
        if not isinstance(node, dict) or depth > 20:
            raise ValueError('Expression must be an object with nesting <=20')
        logical = set(node) & {'all', 'any', 'not'}
        if logical:
            if len(node) != 1:
                raise ValueError('Use exactly one of all, any or not per logical node')
            key = next(iter(logical))
            if key == 'not':
                expression(node[key], depth + 1)
            else:
                if not isinstance(node[key], list) or not node[key]:
                    raise ValueError('all/any need a nonempty expression list')
                for child in node[key]:
                    expression(child, depth + 1)
            return
        if set(node) - {'field', 'op', 'value', 'other_field', 'lag', 'other_lag'}:
            raise ValueError('Unknown predicate keys')
        for key in ('field', 'other_field'):
            if key in node:
                name = node[key]
                parts = name.split('.') if isinstance(name, str) else []
                valid = (len(parts) == 2 and (
                    parts[0] == 'feature' and parts[1].isidentifier()
                    or parts[0] == 'price' and parts[1] in ('open', 'high', 'low', 'close', 'volume')
                    or parts[0] == 'di' and parts[1] in DI_FIELDS
                    or parts[0] == 'event' and parts[1] in EVENT_FIELDS))
                valid |= (len(parts) >= 4 and parts[0] == 'context' and parts[1] in ('1h', '4h', '1d')
                          and parts[2] in ('REGIME', 'TREND', 'STRUCTURE', 'MOMENTUM', 'VOLATILITY', 'PARTICIPATION', 'PHASE', 'LIQUIDITY', 'SENTIMENT', 'BIAS')
                          and all(part.isidentifier() for part in parts[3:]))
                if not valid:
                    raise ValueError('Unsupported field: ' + str(name))
        if 'field' not in node or node.get('op') not in OPS:
            raise ValueError('Predicate needs a field and supported op')
        for key in ('lag', 'other_lag'):
            lag = node.get(key, 0)
            if type(lag) is not int or not 0 <= lag <= 1000:
                raise ValueError('Lag must be an integer from 0 through 1000; future references are forbidden')
        op = node['op']
        if op in ('available', 'missing'):
            if set(node) & {'value', 'other_field', 'other_lag'}:
                raise ValueError('available/missing take no comparison operand')
        elif ('value' in node) == ('other_field' in node):
            raise ValueError('Use exactly one comparison value or other_field')
        if 'other_lag' in node and 'other_field' not in node:
            raise ValueError('other_lag needs other_field')
        if op == 'in' and ('other_field' in node or not isinstance(node.get('value'), list) or not node['value']):
            raise ValueError('in requires a nonempty literal list')
        if 'value' in node:
            values = node['value'] if op == 'in' else [node['value']]
            if any(v is None or not (type(v) in (str, bool) or number(v)) for v in values):
                raise ValueError('Comparison literals must be finite scalar values; use missing for unavailable data')
            if op in ('gt', 'gte', 'lt', 'lte') and not number(node['value']):
                raise ValueError('Ordered comparisons require numeric operands')

    for branch in branches:
        if (not isinstance(branch, dict) or set(branch) != {'id', 'side', 'when'}
                or not isinstance(branch.get('id'), str) or not branch['id'] or branch['id'] in ids):
            raise ValueError('Branches require unique id, side and when')
        ids.add(branch['id'])
        if branch['side'] not in ('BUY', 'SELL'):
            raise ValueError('Branch side must be BUY or SELL')
        expression(branch['when'])
    if {b['side'] for b in branches} != {'BUY', 'SELL'}:
        raise ValueError('Provide at least one BUY and one SELL branch')
    execution = config.get('execution', {})
    if not isinstance(execution, dict) or set(execution) - set(EXECUTION):
        raise ValueError('Unknown execution options')
    for key, value in (EXECUTION | execution).items():
        if not number(value) or (value <= 0 if key == 'initial_capital' else not 0 <= value < 10000):
            raise ValueError('Invalid execution value: ' + key)
    return config


class Memory:
    """Resolve only values known by a closed candle, with explicit missing reasons."""
    def __init__(self, source):
        if (source.get('version') != 'btc-hour-sequence-source-v1'
                or source.get('symbol') != 'BTCUSDT' or source.get('timeframe') != '1h'):
            raise ValueError('Use a row-level BTCUSDT 1h source export')
        self.source = source
        self.rows = source['candles']
        prior = None
        for row in self.rows:
            if (type(row.get('open_time')) is not int or type(row.get('close_time')) is not int
                    or row['close_time'] < row['open_time']
                    or prior is not None and row['open_time'] <= prior
                    or row['close_time'] >= source['observed_as_of']):
                raise ValueError('Candle timestamps must be unique, chronological and closed at the export cutoff')
            prior = row['open_time']
        self.flags = pivot_sequences.events(self.rows)[1]
        self.features = {key for row in self.rows for key in row['features']}

    def price_valid(self, index):
        r = self.rows[index]
        return (r['close_time'] == r['open_time'] + STEP - 1
                and all(number(r[k]) and r[k] > 0 for k in ('open', 'high', 'low', 'close'))
                and r['low'] <= min(r['open'], r['close']) <= max(r['open'], r['close']) <= r['high'])

    @lru_cache(maxsize=65536)
    def value(self, index, field, lag=0):
        at = index - lag
        if at < 0:
            return None, 'INSUFFICIENT_HISTORY'
        if (self.rows[index]['open_time'] - self.rows[at]['open_time'] != lag * STEP
                or any(self.rows[j - 1]['close_time'] + 1 != self.rows[j]['open_time'] for j in range(at + 1, index + 1))):
            return None, 'GAP_IN_LAG'
        row = self.rows[at]
        if not self.price_valid(at):
            return None, 'INVALID_PRICE_CANDLE'
        parts = field.split('.')
        if parts[0] == 'price':
            value = row.get(parts[1]) if self.price_valid(at) else None
        elif parts[0] in ('feature', 'di', 'event'):
            if not row.get('feature_valid') or row['features'].get('measurement_gap'):
                return None, 'INVALID_FEATURE_CANDLE'
            if parts[0] == 'feature':
                value = row['features'].get(parts[1])
            elif parts[0] == 'event':
                value = self.flags[at].get(parts[1])
            else:
                value = (pivot_sequences.context(row) or {}).get(parts[1])
        else:
            frame, engine = parts[1:3]
            history = self.source.get('engine_history', {}).get(frame + ':' + engine, {})
            step = {'1h': STEP, '4h': 4 * STEP, '1d': 24 * STEP}[frame]
            known = row['close_time'] + 1
            opened = known // step * step - step
            payload = history.get('results', {}).get(str(opened))
            if not payload:
                return None, 'MISSING_EXACT_CLOSED_CONTEXT'
            if (payload.get('candle_open_time') != opened or payload.get('candle_close_time') != opened + step - 1
                    or payload.get('as_of') != opened + step):
                return None, 'INVALID_CONTEXT_TIME'
            if payload.get('data_quality') not in ('VALID', 'PARTIAL'):
                return None, 'INVALID_CONTEXT_QUALITY'
            value = payload.get('classification') or {}
            for key in parts[3:]:
                value = value.get(key) if isinstance(value, dict) else None
        if value is None or isinstance(value, (dict, list)) or isinstance(value, float) and not math.isfinite(value):
            return None, 'MISSING_VALUE'
        if isinstance(value, str) and value in ('UNKNOWN', 'UNAVAILABLE'):
            return None, 'UNKNOWN_CLASSIFICATION'
        return value, None

    def evaluate(self, node, index, missing):
        if 'all' in node or 'any' in node:
            key = 'all' if 'all' in node else 'any'
            values = [self.evaluate(child, index, missing) for child in node[key]]
            if key == 'all':
                return False if False in values else UNKNOWN if UNKNOWN in values else True
            return True if True in values else UNKNOWN if UNKNOWN in values else False
        if 'not' in node:
            value = self.evaluate(node['not'], index, missing)
            return UNKNOWN if value is UNKNOWN else not value
        left, reason = self.value(index, node['field'], node.get('lag', 0))
        if reason:
            missing.add(node['field'] + ':' + reason)
        op = node['op']
        if op in ('available', 'missing'):
            return (reason is None) if op == 'available' else (reason is not None)
        if 'other_field' in node:
            right, other_reason = self.value(index, node['other_field'], node.get('other_lag', 0))
            if other_reason:
                missing.add(node['other_field'] + ':' + other_reason)
            reason = reason or other_reason
        else:
            right = node['value']
        if reason:
            return UNKNOWN
        if op in ('gt', 'gte', 'lt', 'lte'):
            if not number(left) or not number(right):
                missing.add(node['field'] + ':NON_NUMERIC_COMPARISON')
                return UNKNOWN
            return {'gt': left > right, 'gte': left >= right, 'lt': left < right, 'lte': left <= right}[op]
        # Booleans must not silently equal numeric 0/1.
        equal = lambda a, b: (type(a) is bool) == (type(b) is bool) and a == b
        if op == 'in':
            return any(equal(left, v) for v in right)
        return equal(left, right) if op == 'eq' else not equal(left, right)


def summarize(trades, capital):
    counts = Counter(t['status'] for t in trades)
    closed = [t for t in trades if t['status'] == 'CLOSED']
    wins = [t for t in closed if t['net_pct'] > 0]
    losses = [t for t in closed if t['net_pct'] < 0]
    balance = peak = capital
    drawdown = 0.
    cash_wins = cash_losses = 0.
    for trade in closed:
        profit = balance * trade['net_pct'] / 100
        cash_wins += max(0, profit)
        cash_losses += max(0, -profit)
        balance *= 1 + trade['net_pct'] / 100
        peak = max(peak, balance)
        drawdown = max(drawdown, (peak - balance) / peak * 100)
    gross_wins = sum(t['net_pct'] for t in wins)
    gross_losses = -sum(t['net_pct'] for t in losses)
    return dict(entries=len(trades), closed=len(closed), open=counts['OPEN'], censored=counts['CENSORED'],
                wins=len(wins), losses=len(losses), breakeven=len(closed) - len(wins) - len(losses),
                win_rate_pct=100 * len(wins) / len(closed) if closed else None,
                mean_net_pct=sum(t['net_pct'] for t in closed) / len(closed) if closed else None,
                sum_trade_net_pct=sum(t['net_pct'] for t in closed),
                profit_factor=cash_wins / cash_losses if cash_losses else None,
                trade_return_profit_factor=gross_wins / gross_losses if gross_losses else None,
                closed_trade_net_profit=balance-capital,
                closed_trade_balance=balance, closed_trade_return_pct=(balance / capital - 1) * 100,
                closed_trade_max_drawdown_pct=drawdown,
                equity_scope='Full-balance fractional spot compounding of closed trades only; excludes open/censored positions; drawdown at completed trades, not intratrade')


def analyze(source, config, *, since=None, until=None):
    validate_config(config)
    memory = Memory(source)
    rows = memory.rows
    execution = EXECUTION | config.get('execution', {})
    for value in (since, until):
        if value is not None and type(value) is not int:
            raise ValueError('Window boundaries must be integer UTC milliseconds')
    if since is not None and until is not None and since >= until:
        raise ValueError('since must be before until')
    selected = [i for i, r in enumerate(rows) if (since is None or r['close_time'] + 1 >= since)
                and (until is None or r['close_time'] + 1 < until)]
    # Fingerprint only analyzer inputs, never retrospective pivot/outcome labels.
    hasher = hashlib.sha256()
    for row in rows:
        hasher.update(json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
        hasher.update(b'\n')
    hasher.update(digest(source.get('engine_history', {})).encode())
    contract = dict(source_id=source['source_id'], memory_digest=hasher.hexdigest(), observed_as_of=source['observed_as_of'],
                    since=since, until=until, execution=execution, fill='NEXT_CANDLE_OPEN', initial_state='WAIT_BUY')
    config_id = digest(config)
    signals, trades = [], []
    diagnostics = {b['id']: dict(side=b['side'], evaluated=0, true=0, false=0, unknown=0, accepted=0,
                                same_side_suppressed=0, tie_matches=0, missing_fields=Counter()) for b in config['branches']}
    waiting = 'BUY'
    position = pending = None
    invalid_prices = gaps = 0
    fee, slip = execution['fee_bps_per_side'] / 10000, execution['slippage_bps_per_side'] / 10000

    def censor(reason):
        if position is not None:
            position['status'] = 'CENSORED'
            if reason not in position['censor_reasons']:
                position['censor_reasons'].append(reason)

    for i in selected:
        row = rows[i]
        valid = memory.price_valid(i)
        gap = i > selected[0] and rows[i - 1]['close_time'] + 1 != row['open_time']
        if gap:
            gaps += 1
            censor('PRICE_GAP')
        if not valid:
            invalid_prices += 1
            censor('INVALID_PRICE')
        if pending:
            if not valid or gap or pending['known_time'] != row['open_time']:
                pending.update(fill_status='CENSORED', fill_reason='MISSING_NEXT_OPEN')
                censor('MISSING_NEXT_OPEN')
            else:
                fill = row['open'] * (1 + slip if pending['side'] == 'BUY' else 1 - slip)
                pending.update(fill_status='FILLED', fill_time=row['open_time'], fill_price=fill)
                key = 'entry' if pending['side'] == 'BUY' else 'exit'
                position.update({key: fill, key + '_time': row['open_time']})
                if pending['side'] == 'BUY' and position['status'] != 'CENSORED':
                    position['status'] = 'OPEN'
                if pending['side'] == 'SELL' and position['status'] != 'CENSORED':
                    net = (fill * (1 - fee) / (position['entry'] * (1 + fee)) - 1) * 100
                    position.update(status='CLOSED', net_pct=net, outcome='WIN' if net > 0 else 'LOSS' if net < 0 else 'BREAKEVEN')
            if pending['side'] == 'SELL':
                position = None
            pending = None
        if not valid:
            continue
        matches = []
        for branch in config['branches']:
            stats = diagnostics[branch['id']]
            stats['evaluated'] += 1
            missing = set()
            result = memory.evaluate(branch['when'], i, missing)
            stats['missing_fields'].update(missing)
            stats['unknown' if result is UNKNOWN else 'true' if result else 'false'] += 1
            if result is True:
                if branch['side'] == waiting:
                    matches.append(branch['id'])
                else:
                    stats['same_side_suppressed'] += 1
        if not matches:
            continue
        side = waiting
        signal = dict(id=f'{side}:{row["close_time"] + 1}', side=side, candle_open_time=row['open_time'],
                      known_time=row['close_time'] + 1, branch_id=matches[0], matched_branches=matches, fill_status='PENDING')
        operands = set().union(*(expression_operands(b['when']) for b in config['branches'] if b['id'] in matches))
        signal['inputs'] = {f'{field}@lag{lag}': dict(zip(('value', 'missing_reason'), memory.value(i, field, lag)))
                            for field, lag in sorted(operands)}
        signals.append(signal)
        diagnostics[matches[0]]['accepted'] += 1
        for branch_id in matches:
            diagnostics[branch_id]['tie_matches'] += 1
        if side == 'BUY':
            position = dict(id=signal['id'], buy_signal_time=signal['known_time'], buy_branch=matches[0],
                            buy_inputs=signal['inputs'], sell_inputs=None,
                            sell_signal_time=None, sell_branch=None, entry=None, exit=None, entry_time=None, exit_time=None,
                            status='PENDING', net_pct=None, outcome=None, censor_reasons=[])
            trades.append(position)
        else:
            position.update(sell_signal_time=signal['known_time'], sell_branch=matches[0], sell_inputs=signal['inputs'])
        pending = signal
        waiting = 'SELL' if side == 'BUY' else 'BUY'
    if pending:
        pending.update(fill_status='UNFILLED_TAIL', fill_reason='NO_NEXT_CANDLE_IN_WINDOW')
        censor('UNFILLED_TAIL')
    years = sorted({str(datetime.fromtimestamp(rows[i]['close_time'] / 1000, timezone.utc).year) for i in selected})
    yearly = []
    for year in years:
        cohort = [t for t in trades if t['status'] == 'CLOSED' and str(datetime.fromtimestamp(t['exit_time'] / 1000, timezone.utc).year) == year]
        yearly.append(dict(year=year, **summarize(cohort, execution['initial_capital'])))
    fields = sorted({field for b in config['branches'] for field in expression_fields(b['when'])})
    missing_features = [field for field in fields if field.startswith('feature.') and field.split('.')[1] not in memory.features]
    result = dict(version=VERSION, config=config, config_digest=config_id, contract=contract,
                  run_id=digest(dict(contract=contract, config_digest=config_id)), candles_scanned=len(selected), candles_evaluated=len(selected)-invalid_prices,
                  signals=signals, trades=trades, waiting_for=waiting, branch_diagnostics=diagnostics,
                  summary=summarize(trades, execution['initial_capital']), yearly=yearly,
                  invalid_price_candles=invalid_prices, price_gaps=gaps, unavailable_feature_fields=missing_features,
                  fields_used=fields, available_feature_fields=sorted(memory.features),
                  definitions=dict(expression='Three-valued AND/OR/NOT: false AND unknown is false; true OR unknown is true. Missing never becomes zero/neutral',
                                   branches='All branches evaluated at each valid candle close; configuration order breaks same-side ties. One accepted signal per candle, beginning with BUY, then strictly alternating',
                                   fills='Next contiguous valid candle open within the evaluation window; configurable spot fees/slippage, no shorts, stops or forced final exit',
                                   gaps='Missing prices censor held trades and missing next-open fills; preserve alternating signal state, never manufacture a SELL to reset',
                                   success='A completed BUY-to-SELL trade with net return >0 after configured costs',
                                   context='Exact last-closed compatible engine context; VALID/PARTIAL only. Reconstructed close-time knowledge, not proof of live publication',
                                   chronology='One continuous replay; yearly closed-trade summaries assigned by SELL fill year, no annual state reset. Inspected research data, not an untouched holdout'))
    return result


def expression_fields(node):
    if 'all' in node or 'any' in node:
        return set().union(*(expression_fields(n) for n in node.get('all', node.get('any'))))
    if 'not' in node:
        return expression_fields(node['not'])
    return {node[k] for k in ('field', 'other_field') if k in node}


def expression_operands(node):
    if 'all' in node or 'any' in node:
        return set().union(*(expression_operands(n) for n in node.get('all', node.get('any'))))
    if 'not' in node:
        return expression_operands(node['not'])
    return {(node[key], node.get(lag, 0)) for key, lag in (('field', 'lag'), ('other_field', 'other_lag')) if key in node}


def compare(baseline, revision):
    """Diagnose old failures after full replay; never select trading rows by outcome."""
    if baseline.get('version') != VERSION or revision.get('version') != VERSION or baseline['contract'] != revision['contract']:
        raise ValueError('Comparison requires identical source memory, time window, initial state and execution costs')
    newer = {t['buy_signal_time']: t for t in revision['trades']}
    older = {t['buy_signal_time']: t for t in baseline['trades']}
    groups = {key: [] for key in ('success_preserved', 'success_lost', 'success_unresolved', 'failure_corrected',
                                  'failure_removed', 'failure_persisted', 'failure_unresolved', 'baseline_unresolved', 'baseline_breakeven', 'new_entries')}
    for old in baseline['trades']:
        new = newer.get(old['buy_signal_time'])
        if old['status'] != 'CLOSED':
            key = 'baseline_unresolved'
        elif old['net_pct'] == 0:
            key = 'baseline_breakeven'
        elif old['net_pct'] > 0:
            key = 'success_lost' if new is None else 'success_unresolved' if new['status'] != 'CLOSED' else 'success_preserved' if new['net_pct'] > 0 else 'success_lost'
        else:
            key = 'failure_removed' if new is None else 'failure_unresolved' if new['status'] != 'CLOSED' else 'failure_corrected' if new['net_pct'] > 0 else 'failure_persisted'
        groups[key].append(dict(buy_signal_time=old['buy_signal_time'], baseline=old, revision=new))
    groups['new_entries'] = [t for t in revision['trades'] if t['buy_signal_time'] not in older]
    return dict(baseline_run_id=baseline['run_id'], revision_run_id=revision['run_id'],
                baseline_config=baseline['config'], baseline_config_digest=baseline['config_digest'],
                counts={key: len(value) for key, value in groups.items()}, groups=groups,
                baseline_summary=baseline['summary'], revision_summary=revision['summary'],
                interpretation='Match by accepted BUY knowledge time. Corrected failure means the same BUY now closes profitably; removed failures are not counted as corrected. Changed entries are removed plus new, not paired counterfactual profits. Full replay precedes failure-subset diagnosis; old outcomes are never rule inputs.')
