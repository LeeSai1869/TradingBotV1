"""Offline current-move pivot trial. No production engines or database access."""
from decimal import Decimal
from Section_12_Research.experiments.pivot_confirmation.trial import seed_from_row
D=lambda value:Decimal(str(value))
RATIO=D('.25')


def simulate(rows,*,closes=2,seed=None,reference="current_move"):
    if reference not in ('current_move','confirmed_pair'):raise ValueError('Unknown reference')
    if closes not in (0,2):raise ValueError('Experiment supports 0 or 2 reverse closes')
    if len(rows)<2:raise ValueError('At least two candles required')
    seed=seed or seed_from_row(rows[0]);pair=[D(p) for p in seed['pair']]
    direction=seed['direction'];candidate=dict(seed['candidate']);candidate['price']=D(candidate['price'])
    if direction not in (-1,1) or len(pair)!=2 or pair[0]==pair[1] or any(not p.is_finite() or p<=0 for p in pair):raise ValueError('Invalid confirmed-pair seed')
    if not candidate['price'].is_finite() or candidate['price']<=0 or candidate['origin']>rows[0]['open_time']:raise ValueError('Invalid or future candidate seed')
    streak=0;opposite=None;events=[];states=[];previous=rows[0];seen=[previous]
    def span():return abs(candidate['price']-pair[-1]) if reference=='current_move' else abs(pair[-1]-pair[-2])
    def state(row):
        distance=span();level=candidate['price']-direction*RATIO*distance
        return dict(open_time=row['open_time'],direction=direction,candidate_price=float(candidate['price']),candidate_time=candidate['origin'],
                    anchor_price=float(pair[-1]),reference_range=float(distance),threshold=float(level),reverse_closes=streak)
    states.append(state(previous))
    duration=previous['close_time']-previous['open_time']+1
    for row in rows[1:]:
        seen.append(row)
        if row['open_time']!=previous['close_time']+1:raise ValueError('Candle gap: cannot establish consecutive-close evidence')
        if row['close_time']-row['open_time']+1!=duration:raise ValueError('Mixed candle durations')
        extreme=D(row['high' if direction==1 else 'low']);value=D(row['close']);prior_close=D(previous['close'])
        extended=extreme>candidate['price'] if direction==1 else extreme<candidate['price']
        if extended:
            candidate=dict(price=extreme,origin=row['open_time']);streak=0;opposite=None
        else:
            reverse=value<prior_close if direction==1 else value>prior_close
            streak=streak+1 if reverse and row['open_time']>candidate['origin'] else 0
            # Preserve the opposite extreme since the candidate's ORIGIN,
            # excluding its own candle (unknown intrabar high/low ordering).
            other=D(row['low' if direction==1 else 'high'])
            if opposite is None or (other<opposite['price'] if direction==1 else other>opposite['price']):
                opposite=dict(price=other,origin=row['open_time'])
            distance=span();threshold=candidate['price']-direction*RATIO*distance
            crossed=value<=threshold if direction==1 else value>=threshold
            if distance>0 and crossed and streak>=closes and row['open_time']>candidate['origin']:
                events.append(dict(type='PIVOT_HIGH' if direction==1 else 'PIVOT_LOW',price=float(candidate['price']),
                    origin_time=candidate['origin'],confirmation_time=row['open_time'],known_time=row['close_time']+1,
                    confirmation_close=float(value),anchor_price=float(pair[-1]),reference_range=float(distance),threshold=float(threshold),reverse_closes=streak))
                pair=[pair[-1],candidate['price']];direction=-direction
                candidate=opposite;streak=0
                # The activated candidate may originate before this confirmation.
                # Carry ALL already observed opposite extremes after its origin,
                # not just candles arriving after it became active.
                known=[b for b in seen if b['open_time']>candidate['origin']]
                field='low' if direction==1 else 'high'
                earlier=(min if direction==1 else max)(known,key=lambda b:D(b[field])) if known else None
                opposite=dict(price=D(earlier[field]),origin=earlier['open_time']) if earlier else None
        states.append(state(row));previous=row
    return dict(events=events,states=states,final=states[-1])

