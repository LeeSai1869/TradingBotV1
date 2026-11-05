"""Causal BTC spot event sequence. Never publishes production decisions."""
from collections import deque
import math

VERSION = 'btc-events-v0.3'
TIMEFRAMES = ('5m', '15m', '30m', '1h')
FIELDS = ('measurement_version', 'measurement_config_id', 'measurement_gap',
          'candidate_pivot', 'candidate_pivot_low_price', 'candidate_pivot_low_time',
          'candidate_pivot_high_price', 'candidate_pivot_high_time', 'di_plus', 'di_minus', 'atr')


def valid(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def context(features):
    plus, minus = features['di_plus'], features['di_minus']
    spread = abs(plus - minus)
    return dict(di_plus=plus, di_minus=minus, spread=spread,
                dominant='DI_MINUS' if minus > plus else 'DI_PLUS' if plus > minus else 'NEUTRAL',
                plus_above_spread=plus > spread, minus_above_spread=minus > spread)


def candidate(features, side):
    """Confluence snapshot only: never creates, confirms or cancels a setup."""
    kind = 'low' if side == 'BUY' else 'high'
    price = features.get('candidate_pivot_' + kind + '_price')
    stamp = features.get('candidate_pivot_' + kind + '_time')
    if features.get('candidate_pivot') != (-1 if side == 'BUY' else 1):
        return None
    return dict(type='CANDIDATE_' + kind.upper(), price=price, origin_time=stamp) if valid(price) and valid(stamp) else None


def turns(before, peak, after):
    """Each DI independently. No plateau guesses; know a turn only at third close."""
    result = []
    for channel in ('di_plus', 'di_minus'):
        a, b, c = (r['features'][channel] for r in (before, peak, after))
        kind = 'PEAK' if a < b > c else 'TROUGH' if a > b < c else None
        if kind:
            result.append(dict(type=channel.upper() + '_' + kind, channel=channel,
                               origin_time=peak['open_time'], time=after['open_time'],
                               known_time=after['close_time'] + 1, values=[a, b, c],
                               at_turn=context(peak['features']), at_detection=context(after['features'])))
    return result


def simulate(rows, *, detail_since=None):
    trades, levels, observations, events = [], [], [], []
    history = deque(maxlen=2)
    position = pending = None
    gaps = 0
    event_serial = 0

    def retain_detail(stamp):
        return detail_since is None or stamp >= detail_since

    def record_event(record):
        nonlocal event_serial
        record['id'] = f'{VERSION}:{record["time"]}:{event_serial}'
        event_serial += 1
        if retain_detail(record['time']):
            events.append(record)
        return record
    fee, slip = .0004, .0002

    def event(kind, row, **details):
        return record_event(dict(type=kind, time=row['open_time'],
                                 known_time=row['close_time'] + 1, **details))

    def close(row, reference, reason):
        nonlocal position
        fill = reference * (1 - slip)
        position.update(exit_time=row['open_time'], exit=fill, status='CLOSED', reason=reason,
                        net_pct=(fill * (1-fee) / (position['entry'] * (1+fee)) - 1) * 100)
        position = None

    for row in rows:
        f, t = row['features'], row['open_time']
        o, h, l, c = (row[k] for k in ('open', 'high', 'low', 'close'))
        continuous = not history or history[-1]['close_time'] + 1 == t
        usable = (all(valid(v) and v > 0 for v in (o, h, l, c))
                  and l <= min(o, c) <= max(o, c) <= h
                  and all(valid(f.get(k)) and f[k] >= 0 for k in ('di_plus', 'di_minus', 'atr'))
                  and f['atr'] > 0 and not f.get('measurement_gap'))
        if not continuous or not usable:
            gaps += 1
            if position:
                position.update(status='CENSORED', exit_time=t, reason='Missing or invalid candle/features')
            event('SEQUENCE_RESET', row, reason='Missing or invalid candle/features')
            position = pending = None
            history.clear()
            continue

        # Pending orders depend only on the previous close. Protective gap stops
        # outrank discretionary exits; current close cannot change the open fill.
        if position and o <= position['stop']:
            close(row, o, 'Trailing stop' if position['stop'] > position['hard_stop'] else 'Hard stop')
            if pending and pending['side'] == 'SELL':
                pending = None
        if pending:
            action = pending
            pending = None
            if action['side'] == 'SELL' and position:
                position['exit_confirmation_time'] = action['confirmation_time']
                position['exit_setup_event_id'] = action['event_id']
                position['exit_trigger_context'] = action['context']
                position['exit_confirmation_context'] = action['confirmation_context']
                close(row, o, 'Dominant DI+ three-candle peak')
            elif action['side'] == 'BUY' and not position:
                entry = o * (1+slip)
                position = dict(entry_time=t, entry=entry, hard_stop=entry*.995, stop=entry*.995,
                                peak=entry, status='OPEN', setup_time=action['time'],
                                setup_event_id=action['event_id'], confirmation_time=action['confirmation_time'],
                                trigger_context=action['context'], di_peak_context=action['peak_context'],
                                confirmation_context=action['context'],
                                candidate_confluence=action['candidate'], price_confluence=action['price_confluence'],
                                entry_reason='Dominant DI- three-candle peak confirmed at third close')
                trades.append(position)
        if position:
            stop = position['stop']
            if retain_detail(t):
                levels.append(dict(time=t, entry_time=position['entry_time'], stop=stop,
                                   hard_stop=position['hard_stop'], entry=position['entry']))
            if l <= stop:
                close(row, stop, 'Trailing stop' if stop > position['hard_stop'] else 'Hard stop')
            else:
                position['peak'] = max(position['peak'], h)
                if c >= position['entry']*1.005:
                    # Only effective next bar. No retroactive favorable fills.
                    position['stop'] = min(c, max(stop, position['peak'] - 1.5*f['atr'],
                                                   position['entry']*(1+fee)/(1-fee)/(1-slip)))

        detected = turns(history[0], history[1], row) if len(history) == 2 else []
        for turn in detected:
            record_event(turn)
        gate = context(f)['dominant']
        side = 'SELL' if position else 'BUY'
        channel = 'di_plus' if side == 'SELL' else 'di_minus'
        expected_gate = channel.upper()
        for turn in detected:
            if (turn['type'] == channel.upper()+'_PEAK' and gate == expected_gate
                    and turn['at_turn']['dominant'] == expected_gate):
                # Price is observed confluence, never an entry/exit gate. A DI
                # turn is already confirmed at this close; no later bar is needed.
                price_confluence = dict(close=c, high=h, low=l,
                    close_above_previous_high=c > history[-1]['high'],
                    close_below_previous_low=c < history[-1]['low'])
                record = event(side+'_CONFIRMED', row, confirmation_basis='DI_TURN_ONLY',
                               turn_origin_time=turn['origin_time'], turn_event_id=turn['id'],
                               context=context(f), peak_context=turn['at_turn'],
                               candidate_confluence=candidate(f, side), price_confluence=price_confluence)
                pending = dict(side=side, time=t, event_id=record['id'],
                               confirmation_time=record['known_time'], context=context(f),
                               peak_context=turn['at_turn'], confirmation_context=context(f),
                               candidate=candidate(f, side), price_confluence=price_confluence)
                if retain_detail(t):
                    observations.append(dict(time=t, price=l if side == 'BUY' else h,
                                             type=side+' DI CONFIRMED'))
                break
        history.append(row)

    closed = [trade for trade in trades if trade['status'] == 'CLOSED']
    realized_balance = 100.
    for trade in closed:
        realized_balance *= 1 + trade['net_pct']/100
    return dict(version=VERSION, trades=trades, levels=levels, observations=observations, events=events,
                gaps=gaps, status='READY', candles=len(rows),
                summary=dict(entries=len(trades), closed=len(closed), open=sum(t['status']=='OPEN' for t in trades),
                             censored=sum(t['status']=='CENSORED' for t in trades),
                             wins=sum(t['net_pct']>0 for t in closed),
                             starting_capital_usd=100., realized_balance_usd=realized_balance,
                             balance_basis='Full-balance fractional spot compounding of closed trades only; open/censored positions excluded',
                             mean_net_pct=sum(t['net_pct'] for t in closed)/len(closed) if closed else None),
                interpretation='Experimental spot event sequence; independent timeframe; starts flat at history boundary. No orders or alerts. Confidence is not a win probability.',
                costs=dict(fee_bps_per_side=4, slippage_bps_per_side=2),
                rules=dict(hard_stop_pct=.5, trailing_activation_pct=.5, trailing_atr=1.5,
                           price_role='CONFLUENCE_ONLY', candidate_role='CONFLUENCE_ONLY',
                           breakout_crash_override='DEFERRED',
                           buy_trigger='DOMINANT_DI_MINUS_THREE_CANDLE_PEAK',
                           sell_trigger='DOMINANT_DI_PLUS_THREE_CANDLE_PEAK',
                           confirmation='DI_THREE_CANDLE_TURN_AT_THIRD_CLOSE', fill='NEXT_CANDLE_OPEN',
                           price_break_gate=False, chase_gate=False))
