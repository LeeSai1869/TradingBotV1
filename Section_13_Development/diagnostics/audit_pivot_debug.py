"""Audit exported pivot evidence without changing calculations or databases."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path


def read(path):
    raw=Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw)


def audit(stored,chart=None):
    rows=stored['candles'];bytime={r['open_time']:r for r in rows};events=[];errors=[];missed=[]
    for row in rows:
        f=row.get('features') or {};items=json.loads(f.get('structure_events') or '[]')
        pivots=[e for e in items if e.get('type') in ('PIVOT_HIGH','PIVOT_LOW')]
        events.extend(pivots)
        for event in pivots:
            side='high' if event['type']=='PIVOT_HIGH' else 'low'
            origin=bytime.get(event['origin_time'])
            if event['confirmation_time']!=row['open_time'] or event['origin_time']>=row['open_time']:
                errors.append(dict(reason='invalid_confirmation_time',event=event['id']))
            if origin and abs(origin[side]-event['price'])>1e-12:
                errors.append(dict(reason='origin_price_mismatch',event=event['id']))
            anchor=f.get('current_active_pivot_low' if side=='high' else 'current_active_pivot_high')
            if anchor is not None:
                level=event['price']+.25*(anchor-event['price'])
                if (side=='high' and row['close']>level+1e-12) or (side=='low' and row['close']<level-1e-12):
                    errors.append(dict(reason='confirmation_before_25_percent_close',event=event['id']))
        # After a confirmation, the new opposite candidate originates on this
        # candle and is ineligible; audit only older, still-active candidates.
        side='high' if f.get('candidate_pivot')==1 else 'low' if f.get('candidate_pivot')==-1 else None
        if side:
            price=f.get('candidate_pivot_'+side+'_price');origin=f.get('candidate_pivot_'+side+'_time')
            anchor=f.get('current_active_pivot_low' if side=='high' else 'current_active_pivot_high')
            if None not in (price,origin,anchor) and origin<row['open_time']:
                level=price+.25*(anchor-price)
                crossed=row['close']<=level+1e-12 if side=='high' else row['close']>=level-1e-12
                if crossed and not any(e['type']=='PIVOT_'+side.upper() for e in pivots):
                    missed.append(dict(open_time=row['open_time'],side=side,close=row['close'],threshold=level))
    result=dict(candles=len(rows),confirmed_events=dict(Counter(e['type'] for e in events)),
        confirmation_errors=errors,eligible_closes_without_confirmation=missed)
    if chart:
        common=[b for b in chart['bars'] if not b.get('provisional') and b['open_time'] in bytime]
        result['chart']=dict(overlapping_closed_candles=len(common),event_mismatches=[b['open_time'] for b in common
            if b['features'].get('structure_events')!=bytime[b['open_time']]['features'].get('structure_events')])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stored',type=Path);parser.add_argument('--chart',type=Path)
    args=parser.parse_args();print(json.dumps(audit(read(args.stored),read(args.chart) if args.chart else None),indent=2))


if __name__=='__main__':main()
