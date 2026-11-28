"""Offline candle-rule research. Never imports or publishes live decision state."""
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import math
import re

from . import pivot_sequences
from . import strategy_exits, strategy_stages
from .candle_calendar import FRAMES, end as candle_end, latest_closed

VERSION = 'btc-hour-strategy-analyzer-v1'
STEP = 3600000
UNKNOWN = None
OPS = {'eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'available', 'missing'}
DI_FIELDS = {'di_plus', 'di_minus', 'abs_spread', 'signed_spread', 'dominance', 'dominant', 'adx'}
EVENT_FIELDS = {'di_minus_peak', 'di_plus_peak', 'spread_peak', 'di_only_buy_turn', 'di_only_sell_turn'}
EXECUTION = dict(fee_bps_per_side=4., slippage_bps_per_side=2., initial_capital=100., intrabar_path='low_first')


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
        if set(node) - {'field', 'op', 'value', 'other_field', 'lag', 'other_lag', 'stage'}:
            raise ValueError('Unknown predicate keys')
        if node.get('stage','activate') not in ('trigger','activate'):raise ValueError('Condition role must be Trigger or Activate')
        for key in ('field', 'other_field'):
            if key in node:
                name = node[key]
                parts = name.split('.') if isinstance(name, str) else []
                valid = (len(parts) == 2 and (
                    parts[0] in ('feature', 'adcn') and parts[1].isidentifier()
                    or parts[0] == 'price' and parts[1] in ('open', 'high', 'low', 'close', 'volume')
                    or parts[0] == 'di' and parts[1] in DI_FIELDS
                    or parts[0] == 'event' and parts[1] in EVENT_FIELDS))
                valid |= (len(parts) >= 4 and parts[0] == 'context' and parts[1] in FRAMES
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
        if (not isinstance(branch, dict) or not {'id', 'side', 'when'} <= set(branch) or set(branch)-{'id','side','when','action','trail','target_profit_pct','activation_timing','execution_timing'}
                or not isinstance(branch.get('id'), str) or not branch['id'] or branch['id'] in ids):
            raise ValueError('Branches require unique id, side and when')
        ids.add(branch['id'])
        if branch['side'] not in ('BUY', 'SELL'):
            raise ValueError('Branch side must be BUY or SELL')
        if branch.get('execution_timing','next_open')!='next_open':raise ValueError('Regular BUY/SELL execution must use next candle open')
        if branch.get('activation_timing','same_or_later') not in ('same_or_later','later'):raise ValueError('Invalid activation timing')
        action = branch.get('action','MARKET_SELL')
        if action not in ('MARKET_SELL','TRAILING_SELL','TAKE_PROFIT') or branch['side']=='BUY' and ('action' in branch or 'trail' in branch or 'target_profit_pct' in branch):
            raise ValueError('Trailing sell is only available on SELL branches')
        if action=='TRAILING_SELL':
            trail=branch.get('trail',{})
            if set(trail)!={'distance_pct','activation_profit_pct'} or not number(trail['distance_pct']) or not 0<trail['distance_pct']<100 or not number(trail['activation_profit_pct']) or not 0<=trail['activation_profit_pct']<=1000:
                raise ValueError('Trailing sell needs distance_pct >0 and <100, and activation_profit_pct from 0 to 1000')
        elif 'trail' in branch:
            raise ValueError('Trail settings require a trailing-sell branch')
        if action=='TAKE_PROFIT':
            if not number(branch.get('target_profit_pct')) or not 0<branch['target_profit_pct']<=1000:
                raise ValueError('Take profit needs target_profit_pct >0 and <=1000')
        elif 'target_profit_pct' in branch:
            raise ValueError('Profit target requires a take-profit branch')
        expression(branch['when'])
        if strategy_stages.project(branch['when'],'activate') is None:raise ValueError('Each branch needs an Activate condition')
    if {b['side'] for b in branches} != {'BUY', 'SELL'}:
        raise ValueError('Provide at least one BUY and one SELL branch')
    execution = config.get('execution', {})
    if not isinstance(execution, dict) or set(execution) - (set(EXECUTION)|{'hard_stop_pct'}):
        raise ValueError('Unknown execution options')
    for key, value in (EXECUTION | execution).items():
        if key=='hard_stop_pct':
            if value is not None and (not number(value) or not 0<value<100):raise ValueError('Hard stop must be disabled or a percentage between 0 and 100')
            continue
        if key=='intrabar_path':
            if value not in ('low_first','high_first'):raise ValueError('Choose low_first or high_first OHLC order')
            continue
        if not number(value) or (value <= 0 if key == 'initial_capital' else not 0 <= value < 10000):
            raise ValueError('Invalid execution value: ' + key)
    return config


class Memory:
    """Resolve only values known by a closed candle, with explicit missing reasons."""
    def __init__(self, source):
        from .pivot_candle_source import unpack
        source = unpack(source)
        legacy = (source.get('version') == 'btc-hour-sequence-source-v1'
                  and source.get('symbol') == 'BTCUSDT' and source.get('timeframe') == '1h')
        general = (source.get('version') in ('pivot-candle-source-v1','memory-candle-source-v1')
                   and re.fullmatch(r'[A-Z0-9]{2,30}USDT', source.get('symbol', ''))
                   and source.get('timeframe') in FRAMES)
        if not (legacy or general):
            raise ValueError('Use a supported row-level spot candle source export')
        self.step = FRAMES[source['timeframe']]
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
        self.value = lru_cache(maxsize=65536)(self._value)

    def price_valid(self, index):
        r = self.rows[index]
        return (r['close_time'] == candle_end(r['open_time'],self.source['timeframe']) - 1
                and all(number(r[k]) and r[k] > 0 for k in ('open', 'high', 'low', 'close'))
                and r['low'] <= min(r['open'], r['close']) <= max(r['open'], r['close']) <= r['high'])

    def _value(self, index, field, lag=0):
        at = index - lag
        if at < 0:
            return None, 'INSUFFICIENT_HISTORY'
        if any(self.rows[j - 1]['close_time'] + 1 != self.rows[j]['open_time'] for j in range(at + 1, index + 1)):
            return None, 'GAP_IN_LAG'
        row = self.rows[at]
        if not self.price_valid(at):
            return None, 'INVALID_PRICE_CANDLE'
        parts = field.split('.')
        if parts[0] == 'price':
            value = row.get(parts[1]) if self.price_valid(at) else None
        elif parts[0] == 'adcn':
            value = row.get('adcn',{}).get(parts[1])
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
            known = row['close_time'] + 1
            opened = latest_closed(known,frame)
            boundary = candle_end(opened,frame)
            payload = history.get('results', {}).get(str(opened))
            if frame == self.source['timeframe'] and opened == row['open_time']:
                payload = row.get('context', {}).get(engine) or payload
            if not payload:
                return None, 'MISSING_EXACT_CLOSED_CONTEXT'
            if (payload.get('candle_open_time') != opened or payload.get('candle_close_time') != boundary - 1
                    or payload.get('as_of') != boundary):
                return None, 'INVALID_CONTEXT_TIME'
            if payload.get('data_quality') not in ('VALID', 'PARTIAL'):
                return None, 'INVALID_CONTEXT_QUALITY'
            output = parts[3]=='output'
            value = payload if output else payload.get('classification') or {}
            for key in parts[4:] if output else parts[3:]:
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


def analyze(source, config, *, since=None, until=None, report_fields=None, progress=None):
    validate_config(config)
    report_fields = sorted(set(report_fields or []))
    if len(report_fields) > 100:
        raise ValueError('Record at most 100 extra report inputs')
    for field in report_fields:
        probe = dict(config, branches=[dict(b, when=dict(field=field, op='available')) for b in config['branches']])
        validate_config(probe)
    memory = Memory(source)
    rows = memory.rows
    trailing = [b for b in config['branches'] if b.get('action')=='TRAILING_SELL']
    standing = [b for b in config['branches'] if b.get('action') in ('TRAILING_SELL','TAKE_PROFIT')]
    risk_budget = .5 if source.get('version') in ('pivot-candle-source-v1','memory-candle-source-v1') or standing else None
    execution = EXECUTION | config.get('execution', {})
    if 'hard_stop_pct' in execution:risk_budget=execution['hard_stop_pct']
    for value in (since, until):
        if value is not None and type(value) is not int:
            raise ValueError('Window boundaries must be integer UTC milliseconds')
    if since is not None and until is not None and since >= until:
        raise ValueError('since must be before until')
    selected = [i for i, r in enumerate(rows) if (since is None or r['close_time'] + 1 >= since)
                and (until is None or r['close_time'] + 1 < until)]
    # Fingerprint only analyzer inputs, never retrospective pivot/outcome labels.
    hasher = hashlib.sha256()
    if hasattr(rows, 'packed'):
        hasher.update(digest(dict(columns=rows.columns, contexts=rows.contexts)).encode())
    for row in (rows.packed if hasattr(rows, 'packed') else rows):
        hasher.update(json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
        hasher.update(b'\n')
    hasher.update(digest(source.get('engine_history', {})).encode())
    contract = dict(source_id=source['source_id'], memory_digest=hasher.hexdigest(), observed_as_of=source['observed_as_of'],
                    symbol=source['symbol'], timeframe=source['timeframe'],
                    risk_budget_pct=risk_budget,
                    since=since, until=until, execution=execution, fill='NEXT_CANDLE_OPEN', initial_state='WAIT_BUY')
    config_id = digest(config)
    signals, trades = [], []
    programs={b['id']:(strategy_stages.project(b['when'],'trigger'),strategy_stages.project(b['when'],'activate')) for b in config['branches']}
    armed={};setup_events=[]
    diagnostics = {b['id']: dict(side=b['side'], evaluated=0, true=0, false=0, unknown=0, accepted=0,
                                same_side_suppressed=0, setups_armed=0, waiting_activation=0, tie_matches=0, missing_fields=Counter()) for b in config['branches']}
    waiting = 'BUY'
    position = pending = None
    invalid_prices = gaps = 0
    fee, slip = execution['fee_bps_per_side'] / 10000, execution['slippage_bps_per_side'] / 10000
    if risk_budget is not None and 1 - (1-fee)*(1-slip)/((1+fee)*(1+slip)) >= risk_budget/100:
        raise ValueError('Configured round-trip costs exhaust the 0.5% loss budget before any price movement')

    def censor(reason):
        if position is not None:
            position['status'] = 'CENSORED'
            if reason not in position['censor_reasons']:
                position['censor_reasons'].append(reason)

    def reset_setups(reason,known_time,completed=None):
        for identity,setup in armed.items():
            if identity!=completed:setup_events.append(dict(type='RESET',reason=reason,known_time=known_time,branch_id=identity,side=setup['side']))
        armed.clear()

    for serial, i in enumerate(selected):
        if progress and serial % 5000 == 0:
            progress(dict(complete=serial, total=len(selected), signals=len(signals)))
        row = rows[i]
        valid = memory.price_valid(i)
        gap = i > selected[0] and rows[i - 1]['close_time'] + 1 != row['open_time']
        if gap:
            reset_setups('PRICE_GAP',row['open_time'])
            gaps += 1
            censor('PRICE_GAP')
        if not valid:
            reset_setups('INVALID_PRICE',row['open_time'])
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
                    if risk_budget is not None:
                        # Exit trigger accounts for both fees and exit slippage.
                        # Entry already includes its modeled slippage.
                        position['stop_price'] = fill * (1 + fee) * (1 - risk_budget / 100) / ((1 - fee) * (1 - slip))
                if pending['side'] == 'SELL' and position['status'] != 'CENSORED':
                    net = (fill * (1 - fee) / (position['entry'] * (1 + fee)) - 1) * 100
                    position.update(status='CLOSED', net_pct=net, outcome='WIN' if net > 0 else 'LOSS' if net < 0 else 'BREAKEVEN')
            if pending['side'] == 'SELL':
                position = None
            pending = None
        if not valid:
            continue
        automatic_exit = None
        if (risk_budget is not None or standing) and position is not None and position['status']=='OPEN':
            eligible = [b for b in standing if i>0 and rows[i-1]['close_time']+1==row['open_time'] and strategy_stages.match(memory,b,programs[b['id']],i-1,armed,set()) is True]
            was_armed=position.get('trail_branch')
            automatic_exit = strategy_exits.walk(position,row,eligible,fee,slip,execution['intrabar_path'])
            if position.get('trail_branch') and not was_armed:
                selected_branch=next(b for b in trailing if b['id']==position['trail_branch'])
                position['trail_condition_known_time']=rows[i-1]['close_time']+1
                position['trail_inputs']={f'{field}@lag{lag}':dict(zip(('value','missing_reason'),memory.value(i-1,field,lag))) for field,lag in expression_operands(selected_branch['when'])}
        if automatic_exit:
            exit_price = automatic_exit['raw_price'] * (1 - slip)
            net = (exit_price * (1 - fee) / (position['entry'] * (1 + fee)) - 1) * 100
            known = automatic_exit['time']
            signal = dict(id=f'STOP:{row["open_time"]}', side='SELL', candle_open_time=row['open_time'],
                          known_time=known, branch_id=automatic_exit['branch'], matched_branches=[automatic_exit['branch']],
                          fill_status='FILLED', fill_time=known, fill_price=exit_price,
                          fill_time_precision=automatic_exit['precision'], reason=automatic_exit['reason'],
                          inputs={'risk.stop_price': dict(value=strategy_exits.stop(position)[0], missing_reason=None)})
            setup=armed.get(automatic_exit['branch'])
            if setup:
                signal.update(trigger_known_time=setup['known_time'],trigger_inputs=setup['inputs'])
                setup_events.append(dict(type='ACTIVATE',branch_id=automatic_exit['branch'],side='SELL',known_time=known,trigger_known_time=setup['known_time']))
            signals.append(signal)
            if automatic_exit['branch'] in diagnostics:
                diagnostics[automatic_exit['branch']]['accepted']+=1
            position.update(status='CLOSED', net_pct=net, outcome='WIN' if net > 0 else 'LOSS' if net < 0 else 'BREAKEVEN',
                            sell_signal_time=known, sell_branch=automatic_exit['branch'], sell_inputs=signal['inputs'],sell_trigger_time=signal.get('trigger_known_time'),sell_trigger_inputs=signal.get('trigger_inputs'),exit_reason=automatic_exit['reason'],
                            exit=exit_price, exit_time=known, exit_time_precision=signal['fill_time_precision'])
            position = pending = None
            reset_setups('SIDE_CHANGED',known,automatic_exit['branch'])
            waiting = 'BUY'
            continue
        matches, trail_matches = [], []
        for branch in config['branches']:
            stats = diagnostics[branch['id']]
            stats['evaluated'] += 1
            missing = set()
            before=branch['id'] in armed
            result = strategy_stages.match(memory,branch,programs[branch['id']],i,armed,missing,allow_arm=branch['side']==waiting)
            if not before and branch['id'] in armed:
                stats['setups_armed']+=1;setup_events.append(dict(type='TRIGGER',**armed[branch['id']]))
            if branch['id'] in armed and result is not True:stats['waiting_activation']+=1
            stats['missing_fields'].update(missing)
            stats['unknown' if result is UNKNOWN else 'true' if result else 'false'] += 1
            if result is True:
                if branch['side'] == waiting:
                    if branch.get('action')=='TAKE_PROFIT':
                        pass  # A new close-time condition applies from the next candle.
                    elif branch.get('action')=='TRAILING_SELL':
                        trail_matches.append(branch)
                    else:
                        matches.append(branch['id'])
                else:
                    stats['same_side_suppressed'] += 1
        if trail_matches and position is not None and position['status']=='OPEN':
            was_armed=position.get('trail_branch')
            strategy_exits.arm_at_close(position,row,trail_matches,fee,slip)
            if position.get('trail_branch') and not was_armed:
                selected_branch=next(b for b in trailing if b['id']==position['trail_branch'])
                position['trail_condition_known_time']=row['close_time']+1
                position['trail_inputs']={f'{field}@lag{lag}':dict(zip(('value','missing_reason'),memory.value(i,field,lag))) for field,lag in expression_operands(selected_branch['when'])}
        if not matches:
            continue
        side = waiting
        signal = dict(id=f'{side}:{row["close_time"] + 1}', side=side, candle_open_time=row['open_time'],
                      known_time=row['close_time'] + 1, branch_id=matches[0], matched_branches=matches, fill_status='PENDING')
        setup=armed.get(matches[0])
        if setup:
            signal.update(trigger_known_time=setup['known_time'],trigger_candle_time=setup['candle_open_time'],trigger_inputs=setup['inputs'])
            setup_events.append(dict(type='ACTIVATE',branch_id=matches[0],side=side,known_time=signal['known_time'],trigger_known_time=setup['known_time']))
        operands = set().union(*(expression_operands(b['when']) for b in config['branches'] if b['id'] in matches))
        operands.update((field, 0) for field in report_fields)
        signal['inputs'] = {f'{field}@lag{lag}': dict(zip(('value', 'missing_reason'), memory.value(i, field, lag)))
                            for field, lag in sorted(operands)}
        signals.append(signal)
        diagnostics[matches[0]]['accepted'] += 1
        for branch_id in matches:
            diagnostics[branch_id]['tie_matches'] += 1
        if side == 'BUY':
            position = dict(id=signal['id'], buy_signal_time=signal['known_time'], buy_branch=matches[0],
                            buy_inputs=signal['inputs'], buy_trigger_time=signal.get('trigger_known_time'),buy_trigger_inputs=signal.get('trigger_inputs'),sell_inputs=None,
                            sell_signal_time=None, sell_branch=None, entry=None, exit=None, entry_time=None, exit_time=None,
                            status='PENDING', net_pct=None, outcome=None, censor_reasons=[])
            trades.append(position)
        else:
            position.update(sell_signal_time=signal['known_time'], sell_branch=matches[0], sell_inputs=signal['inputs'],sell_trigger_time=signal.get('trigger_known_time'),sell_trigger_inputs=signal.get('trigger_inputs'))
        reset_setups('SIDE_CHANGED',signal['known_time'],matches[0])
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
    buys=[b for b in diagnostics.values() if b['side']=='BUY']
    blocked=bool(buys) and not signals and all(b['evaluated']>0 and b['unknown']==b['evaluated'] for b in buys)
    result = dict(version=VERSION, config=config, config_digest=config_id, contract=contract,
                  run_id=digest(dict(contract=contract, config_digest=config_id)), candles_scanned=len(selected), candles_evaluated=len(selected)-invalid_prices,
                  test_status='BLOCKED_INPUTS' if blocked else 'COMPLETED',
                  signals=signals, trades=trades, setup_events=setup_events,pending_setups=list(armed.values()),waiting_for=waiting, branch_diagnostics=diagnostics,
                  summary=summarize(trades, execution['initial_capital']), yearly=yearly,
                  invalid_price_candles=invalid_prices, price_gaps=gaps, unavailable_feature_fields=missing_features,
                  fields_used=fields, report_fields=report_fields, available_feature_fields=sorted(memory.features),
                  definitions=dict(expression='Three-valued AND/OR/NOT: false AND unknown is false; true OR unknown is true. Missing never becomes zero/neutral',
                                   branches='Conditions marked Trigger latch a branch setup; conditions marked Activate execute at the same or a later known close by default, with optional later-close-only timing. Logical groups are projected within each stage. Setups have no expiry and reset on side changes or missing/invalid price candles. Unmarked branches retain ordinary close matching; configuration order breaks same-side ties. One accepted signal per candle, beginning with BUY, then strictly alternating',
                                   fills='Rule signals fill at the next contiguous valid candle open within the evaluation window; configurable spot fees/slippage, no shorts or forced final exit. New spot candle sources additionally execute the standing risk stop described below',
                                   risk='Hard stop is controlled by execution.hard_stop_pct: null disables it; a percentage enables it. Omitted values retain legacy source defaults (0.5% for spot/standing-exit sources). The resolved setting is contract.risk_budget_pct. Fees/slippage are included; adverse opens may exceed the budget. Standing exit touches have unknown intrabar timing.',
                                   trailing='Trailing SELL branches arm when net liquidation profit reaches the activation threshold AND their condition is known true. Intrabar eligibility uses the previous closed candle; newly true close-time conditions arm for the next candle. Once armed, never disarm. Trail follows the highest raw price since entry. OHLC path is an explicit assumption, not tick reconstruction.',
                                   gaps='Missing prices censor held trades and missing next-open fills; preserve alternating signal state, never manufacture a SELL to reset',
                                   success='A completed BUY-to-SELL trade with net return >0 after configured costs',
                                   context='Exact last-closed compatible engine context; VALID/PARTIAL only. Reconstructed close-time knowledge, not proof of live publication',
                                   chronology='One continuous replay; yearly closed-trade summaries assigned by SELL fill year, no annual state reset. Inspected research data, not an untouched holdout'))
    if progress:
        progress(dict(complete=len(selected), total=len(selected), signals=len(signals)))
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
