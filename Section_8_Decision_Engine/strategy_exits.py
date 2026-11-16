"""Standing spot stops and causal trailing orders over explicit OHLC paths."""


def trigger_price(position, profit_pct, fee, slip):
    return position['entry'] * (1+fee) * (1+profit_pct/100) / ((1-fee)*(1-slip))


def arm(position, branch, price, at, precision):
    position.update(trail_branch=branch['id'], trail_distance_pct=branch['trail']['distance_pct'],
                    trail_armed_at=at, trail_arm_price=price, trail_arm_time_precision=precision)


def stop(position):
    hard = position.get('stop_price')
    trailing = position['peak']*(1-position['trail_distance_pct']/100) if position.get('trail_branch') else None
    if trailing is not None and (hard is None or trailing > hard):
        return trailing, position['trail_branch'], 'TRAILING_STOP'
    return hard, 'RISK_STOP', 'HARD_STOP'


def walk(position, row, eligible, fee, slip, path='low_first'):
    """Eligibility comes only from the preceding closed candle, never this bar."""
    opened, closed = row['open_time'], row['close_time']+1
    position.setdefault('peak', row['open'])
    targets=[(trigger_price(position,b['target_profit_pct'],fee,slip),i,b) for i,b in enumerate(eligible) if b.get('action')=='TAKE_PROFIT']
    eligible=[b for b in eligible if b.get('action')!='TAKE_PROFIT']
    points = [row['open'], row['low'], row['high'], row['close']] if path=='low_first' else [row['open'], row['high'], row['low'], row['close']]

    def exit_at(price, at, precision, branch, reason):
        return dict(raw_price=price, time=at, precision=precision, branch=branch, reason=reason)

    level, branch, reason = stop(position)
    if level is not None and points[0] <= level:
        return exit_at(points[0], opened, 'OPEN', branch, reason)
    for j, price in enumerate(points):
        before = points[j-1] if j else price
        level, branch, reason = stop(position)
        if j and price < before and level is not None and price <= level:
            return exit_at(level, closed, 'WITHIN_CANDLE_UNKNOWN', branch, reason)
        target_hit=min((t for t in targets if price>=t[0]),key=lambda item:(item[0],item[1]),default=None)
        activation_target=min((trigger_price(position,b['trail']['activation_profit_pct'],fee,slip) for b in eligible),default=None) if not position.get('trail_branch') else None
        if target_hit and (activation_target is None or target_hit[0]<=max(before,activation_target)):
            position['peak']=max(position['peak'],target_hit[0])
            return exit_at(target_hit[0],opened if not j else closed,'OPEN' if not j else 'WITHIN_CANDLE_UNKNOWN',target_hit[2]['id'],'TAKE_PROFIT')
        if not position.get('trail_branch') and eligible:
            candidates = [(trigger_price(position,b['trail']['activation_profit_pct'],fee,slip),order,b) for order,b in enumerate(eligible)]
            target, _, chosen = min(candidates, key=lambda item:(item[0],item[1]))
            if price >= target:
                activation = max(before,target) if j and price>=before else price
                position['peak'] = max(position['peak'],activation)
                arm(position,chosen,activation,opened if not j else closed,'OPEN' if not j else 'WITHIN_CANDLE_UNKNOWN')
                level, branch, reason = stop(position)
                if activation <= level:
                    return exit_at(activation,opened if not j else closed,'OPEN' if not j else 'WITHIN_CANDLE_UNKNOWN',branch,reason)
        if target_hit:
            position['peak']=max(position['peak'],target_hit[0])
            return exit_at(target_hit[0],opened if not j else closed,'OPEN' if not j else 'WITHIN_CANDLE_UNKNOWN',target_hit[2]['id'],'TAKE_PROFIT')
        position['peak'] = max(position['peak'],price)
    return None


def arm_at_close(position, row, branches, fee, slip):
    """New close-time conditions may arm an order for the NEXT candle only."""
    if position.get('trail_branch'):
        return
    for branch in branches:
        if row['close'] >= trigger_price(position,branch['trail']['activation_profit_pct'],fee,slip):
            arm(position,branch,row['close'],row['close_time']+1,'CONFIRMED_CLOSE')
            return
