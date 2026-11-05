"""Causal BTC spot event sequence. Never publishes production decisions."""
from collections import deque
import math

VERSION = 'btc-events-v0.2'
TIMEFRAMES = ('5m', '15m', '30m', '1h')
FIELDS = ('measurement_version', 'measurement_config_id', 'measurement_gap',
          'candidate_pivot', 'candidate_pivot_low_price', 'candidate_pivot_low_time',
          'candidate_pivot_high_price', 'candidate_pivot_high_time', 'di_plus', 'di_minus', 'atr')
CONFIRMATION_BARS = 8


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
    position = pending = setup = None
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

    for index, row in enumerate(rows):
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
            position = pending = setup = None
            history.clear()
            continue

        # Pending orders depend only on the previous close. Protective gap stops
        # outrank discretionary exits; current close cannot change the open fill.
        if position and o <= position['stop']:
            close(row, o, 'Trailing stop' if position['stop'] > position['hard_stop'] else 'Hard stop')
            setup = None
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
                close(row, o, 'DI+ peak then later price weakness')
            elif action['side'] == 'BUY' and not position:
                if o > action['low'] and o <= action['trigger'] * 1.005:
                    entry = o * (1+slip)
                    position = dict(entry_time=t, entry=entry, hard_stop=entry*.995, stop=entry*.995,
                                    peak=entry, status='OPEN', setup_time=action['time'],
                                    setup_event_id=action['event_id'], confirmation_time=action['confirmation_time'],
                                    trigger_context=action['context'], di_peak_context=action['peak_context'],
                                    confirmation_context=action['confirmation_context'],
                                    candidate_confluence=action['candidate'],
                                    entry_reason='Dominant DI- three-candle peak then later price recovery')
                    trades.append(position)
                else:
                    event('BUY_REJECTED', row, reason='Opening gap broke setup low or exceeded 0.5% chase limit',
                          setup_event_id=action['event_id'])
        if position:
            stop = position['stop']
            if retain_detail(t):
                levels.append(dict(time=t, entry_time=position['entry_time'], stop=stop,
                                   hard_stop=position['hard_stop'], entry=position['entry']))
            if l <= stop:
                close(row, stop, 'Trailing stop' if stop > position['hard_stop'] else 'Hard stop')
                setup = None
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
        if setup:
            side = setup['side']
            reason = ('Dominance gate changed' if gate != setup['gate'] else
                      'Setup price invalidated' if (l < setup['low'] if side == 'BUY' else h > setup['high']) else
                      'Confirmation expired' if index-setup['index'] > CONFIRMATION_BARS else None)
            if reason:
                event(side+'_CANCELLED', row, reason=reason, setup_event_id=setup['event_id'])
                setup = None
            elif (c > setup['high'] if side == 'BUY' else c < setup['low']):
                # setup is from a strictly earlier candle; DI need not mirror or
                # turn again on this price-confirmation candle.
                record = event(side+'_CONFIRMED', row, setup_event_id=setup['event_id'],
                               context=context(f), price=c, candidate_confluence=candidate(f, side))
                if retain_detail(t):
                    observations.append(dict(time=t, price=c, type=side+' CONFIRMED'))
                pending = dict(setup, trigger=c, confirmation_time=record['known_time'],
                               confirmation_context=context(f), candidate=candidate(f, side) or setup['candidate'])
                setup = None

        if setup is None and pending is None:
            side = 'SELL' if position else 'BUY'
            channel = 'di_plus' if side == 'SELL' else 'di_minus'
            expected_gate = channel.upper()
            for turn in detected:
                if (turn['type'] == channel.upper()+'_PEAK' and gate == expected_gate
                        and turn['at_turn']['dominant'] == expected_gate):
                    low = min(r['low'] for r in (*history, row)) if side == 'BUY' else l
                    high = h if side == 'BUY' else max(r['high'] for r in (*history, row))
                    record = event(side+'_SETUP', row, turn_origin_time=turn['origin_time'],
                                   turn_event_id=turn['id'], confirmation_level=h if side == 'BUY' else l,
                                   invalidation_level=low if side == 'BUY' else high,
                                   context=context(f), peak_context=turn['at_turn'],
                                   candidate_confluence=candidate(f, side))
                    setup = dict(side=side, time=t, index=index, gate=expected_gate, event_id=record['id'],
                                 low=low, high=high, peak_context=turn['at_turn'],
                                 context=context(f), candidate=candidate(f, side))
                    if retain_detail(t):
                        observations.append(dict(time=t, price=l if side == 'BUY' else h, type=side+' SETUP'))
                    break
        history.append(row)

    closed = [trade for trade in trades if trade['status'] == 'CLOSED']
    return dict(version=VERSION, trades=trades, levels=levels, observations=observations, events=events,
                gaps=gaps, status='READY', candles=len(rows),
                summary=dict(entries=len(trades), closed=len(closed), open=sum(t['status']=='OPEN' for t in trades),
                             censored=sum(t['status']=='CENSORED' for t in trades),
                             wins=sum(t['net_pct']>0 for t in closed),
                             mean_net_pct=sum(t['net_pct'] for t in closed)/len(closed) if closed else None),
                interpretation='Experimental spot event sequence; independent timeframe; starts flat at history boundary. No orders or alerts. Confidence is not a win probability.',
                costs=dict(fee_bps_per_side=4, slippage_bps_per_side=2),
                rules=dict(hard_stop_pct=.5, trailing_activation_pct=.5, trailing_atr=1.5,
                           confirmation_bars=CONFIRMATION_BARS, candidate_role='CONFLUENCE_ONLY',
                           buy_trigger='DOMINANT_DI_MINUS_THREE_CANDLE_PEAK',
                           sell_trigger='DOMINANT_DI_PLUS_THREE_CANDLE_PEAK',
                           confirmation='LATER_CLOSE_BEYOND_TRIGGER_CANDLE_PRICE_EXTREME'))
