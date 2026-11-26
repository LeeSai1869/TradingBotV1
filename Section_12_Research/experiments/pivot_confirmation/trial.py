"""Offline pivot experiment. Never imports app engines or opens market databases."""
import argparse
from decimal import Decimal
import gzip
import json
from pathlib import Path

D=lambda value:Decimal(str(value))
RATIO=D('.25')


def seed_from_row(row):
    f=row['features'];last=int(f['last_confirmed_pivot_type'])
    high=D(f['current_active_pivot_high']);low=D(f['current_active_pivot_low'])
    direction=int(f['candidate_pivot']);side='high' if direction==1 else 'low'
    if last not in (-1,1) or direction!=-last or high<=low:raise ValueError('A valid confirmed-pair seed and active opposite candidate are required')
    return dict(pair=[high,low] if last==-1 else [low,high],direction=direction,
                candidate=dict(price=D(f['candidate_pivot_'+side+'_price']),origin=int(f['candidate_pivot_'+side+'_time'])))


def simulate(rows,*,closes=2,seed=None):
    if closes not in (0,2):raise ValueError('Experiment supports 0 or 2 reverse closes')
    if len(rows)<2:raise ValueError('At least two candles required')
    seed=seed or seed_from_row(rows[0]);pair=[D(p) for p in seed['pair']]
    direction=seed['direction'];candidate=dict(seed['candidate']);candidate['price']=D(candidate['price'])
    if direction not in (-1,1) or len(pair)!=2 or pair[0]==pair[1] or any(not p.is_finite() or p<=0 for p in pair):raise ValueError('Invalid confirmed-pair seed')
    if not candidate['price'].is_finite() or candidate['price']<=0 or candidate['origin']>rows[0]['open_time']:raise ValueError('Invalid or future candidate seed')
    streak=0;opposite=None;events=[];states=[];previous=rows[0];seen=[previous]
    def state(row):
        reference=abs(pair[-1]-pair[-2]);level=candidate['price']-direction*RATIO*reference
        return dict(open_time=row['open_time'],direction=direction,candidate_price=float(candidate['price']),candidate_time=candidate['origin'],
                    reference_range=float(reference),threshold=float(level),reverse_closes=streak)
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
            reference=abs(pair[-1]-pair[-2]);threshold=candidate['price']-direction*RATIO*reference
            crossed=value<=threshold if direction==1 else value>=threshold
            if reference>0 and crossed and streak>=closes and row['open_time']>candidate['origin']:
                events.append(dict(type='PIVOT_HIGH' if direction==1 else 'PIVOT_LOW',price=float(candidate['price']),
                    origin_time=candidate['origin'],confirmation_time=row['open_time'],known_time=row['close_time']+1,
                    confirmation_close=float(value),reference_range=float(reference),threshold=float(threshold),reverse_closes=streak))
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


def summarize(events,rows):
    bytime={r['open_time']:i for i,r in enumerate(rows)};times=[e['confirmation_time'] for e in events]
    return dict(confirmations=len(events),highs=sum(e['type']=='PIVOT_HIGH' for e in events),lows=sum(e['type']=='PIVOT_LOW' for e in events),
        confirmations_on_adjacent_candles=sum(bytime[b]-bytime[a]==1 for a,b in zip(times,times[1:])),
        median_recognition_delay_bars=median([(e['confirmation_time']-e['origin_time'])/(rows[0]['close_time']-rows[0]['open_time']+1) for e in events]))


def median(values):
    values=sorted(values);n=len(values)
    return None if not n else values[n//2] if n%2 else (values[n//2-1]+values[n//2])/2


def run(stored):
    rows=stored['candles'];old=[]
    for row in rows[1:]:
        old.extend(e for e in json.loads((row.get('features') or {}).get('structure_events') or '[]') if e.get('type') in ('PIVOT_HIGH','PIVOT_LOW'))
    variants={'current_stored':dict(events=old),'confirmed_pair_only':simulate(rows,closes=0),'confirmed_pair_two_closes':simulate(rows,closes=2)}
    return dict(symbol=stored['symbol'],interval=stored['interval'],first_open_ms=rows[0]['open_time'],last_open_ms=rows[-1]['open_time'],
        seed={**seed_from_row(rows[0]),'note':'Known state at first exported candle; no reconstruction before this boundary.'},
        summary={key:summarize(value['events'],rows) for key,value in variants.items()},variants=variants)


def serial(value):return str(value) if isinstance(value,Decimal) else value


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stored',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();stored=json.loads(gzip.decompress(args.stored.read_bytes()))
    result=run(stored);args.output.write_text(json.dumps(result,default=serial,separators=(',',':')))
    print(json.dumps(result['summary'],indent=2));print('Offline results: '+str(args.output))


if __name__=='__main__':main()
