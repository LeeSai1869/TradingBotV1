"""Compare offline pivot variants on archived exports; never open a database."""
import argparse
from collections import deque
import gzip
import hashlib
import json
from pathlib import Path
from .trial import simulate,D
from Section_12_Research.experiments.pivot_confirmation.trial import seed_from_row,median

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).parent
VARIANTS={'confirmed_pair_two_closes':dict(reference='confirmed_pair',closes=2),
          'current_move_only':dict(reference='current_move',closes=0),
          'current_move_two_closes':dict(reference='current_move',closes=2)}

def shrinking_rows(turns=30):
    values=[100.];position=100.;target=90.
    for _ in range(turns):
        values.extend([(position+target)/2,target])
        position,target=target,(position+target)/2
    rows=[dict(open_time=i*900000,close_time=(i+1)*900000-1,open=v,high=v,low=v,close=v) for i,v in enumerate(values)]
    return rows,dict(pair=[100,80],direction=1,candidate=dict(price=D(100),origin=0))

def archived_seed(source,rows):
    known=sorted((p['pivot'] for p in source['pivots'] if p['pivot']['known_time']<=rows[0]['close_time']+1),key=lambda e:e['known_time'])
    last=known[-1];opposite=next(p for p in reversed(known[:-1]) if p['type']!=last['type'])
    candidates=[r for r in source['candles'] if last['origin_time']<r['open_time']<=rows[0]['open_time']]
    if not candidates:raise ValueError('No observed candidate after seed pivot origin')
    high=last['type']=='PIVOT_LOW';field='high' if high else 'low'
    candidate=(max if high else min)(candidates,key=lambda r:r[field])
    return dict(pair=[opposite['price'],last['price']],direction=1 if high else -1,
                candidate=dict(price=D(candidate[field]),origin=candidate['open_time']))

def metrics(events,rows):
    lookup={r['open_time']:i for i,r in enumerate(rows)}
    lags=[lookup[e['confirmation_time']]-lookup.get(e['origin_time'],0) for e in events if e['origin_time'] in lookup]
    legs=[abs(b['price']-a['price'])/a['price']*100 for a,b in zip(events,events[1:])]
    gaps=[lookup[b['confirmation_time']]-lookup[a['confirmation_time']] for a,b in zip(events,events[1:])]
    # Window labels are descriptive research slices, never pivot conditions.
    sideways=[];trend=[]
    for end in range(63,len(rows),64):
        window=rows[end-63:end+1];travel=sum(abs(b['close']-a['close']) for a,b in zip(window,window[1:]))
        efficiency=abs(window[-1]['close']-window[0]['close'])/travel if travel else 0
        count=sum(window[0]['open_time']<=e['confirmation_time']<=window[-1]['open_time'] for e in events)
        (sideways if efficiency<=.2 else trend).append(count)
    queue=deque();peak=0
    for e in events:
        i=lookup[e['confirmation_time']];queue.append(i)
        while queue and queue[0]<=i-32:queue.popleft()
        peak=max(peak,len(queue))
    return dict(confirmations=len(events),per_100_candles=100*len(events)/len(rows),
                median_confirmation_lag_bars=median(lags),adjacent_confirmations=sum(g==1 for g in gaps),
                minimum_confirmation_spacing_bars=min(gaps) if gaps else None,
                median_leg_pct=median(legs),minimum_leg_pct=min(legs) if legs else None,
                legs_below_0_1_pct=sum(x<.1 for x in legs),legs_below_0_25_pct=sum(x<.25 for x in legs),
                peak_confirmations_in_32_bars=peak,sideways_windows=len(sideways),
                median_confirmations_per_sideways_64_bars=median(sideways))

def compare(rows,seed):
    before=hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()
    results={key:simulate(rows,seed=seed,**options) for key,options in VARIANTS.items()}
    if before!=hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest():raise AssertionError('Input mutated')
    return results,{key:metrics(value['events'],rows) for key,value in results.items()}

def build_view(rows,results,stats,path,label):
    template=(HERE.parent/'pivot_confirmation/viewer.html').read_text()
    template=template.replace('ENAUSDT 15m',label).replace('Research comparison on 6,000 exported candles.',f'Research comparison on {len(rows):,} archived candles.')
    template=template.replace('The proposed rule requires a reversal of at least 25% of the last two confirmed pivots’ range AND two consecutive reverse closes.','Proposed: reverse 25% of the distance between the last confirmed opposite pivot and current candidate, AND two consecutive reverse closes.')
    template=template.replace('<option value="confirmed_pair_two_closes">Proposed: confirmed pair + two closes</option><option value="confirmed_pair_only">Control: confirmed pair without close confluence</option>', '<option value="current_move_two_closes">Current move + two closes</option><option value="current_move_only">Current move without close filter</option>')
    template=template.replace('Current stored SH / SL','Baseline: last confirmed pair + two closes').replace("current_stored:'Current stored',confirmed_pair_only:'Confirmed pair only',confirmed_pair_two_closes:'Confirmed pair + two closes'", "current_stored:'Confirmed pair + two closes',current_move_only:'Current move only',current_move_two_closes:'Current move + two closes'")
    template=template.replace('s.confirmations_on_adjacent_candles','s.adjacent_confirmations').replace('s.median_recognition_delay_bars','s.median_confirmation_lag_bars')
    template=template.replace('<option>6000</option>',f'<option>{len(rows)}</option>')
    variants={'current_stored':results['confirmed_pair_two_closes'],**{k:v for k,v in results.items() if k!='confirmed_pair_two_closes'}}
    summary={'current_stored':stats['confirmed_pair_two_closes'],**{k:v for k,v in stats.items() if k!='confirmed_pair_two_closes'}}
    payload=dict(bars=[{k:r[k] for k in ('open_time','open','high','low','close')} for r in rows],result=dict(variants=variants,summary=summary))
    path.write_text(template.replace('__PAYLOAD__',json.dumps(payload,separators=(',',':')).replace('</','<\\/')))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=HERE/'results');args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    ena_path=ROOT/'Section_12_Research/reports/pivot_debug/ENAUSDT-15m-20261126/stored-pivots.json.gz'
    btc_path=ROOT/'Section_12_Research/reports/BTC_1h_sequences/source_v1.json.gz'
    datasets=[]
    for name,path in [('ENAUSDT_15m',ena_path),('BTCUSDT_1h',btc_path)]:
        data=path.read_bytes();source=json.loads(gzip.decompress(data));rows=source['candles'] if name.startswith('ENA') else source['candles'][-12000:]
        seed=seed_from_row(rows[0]) if name.startswith('ENA') else archived_seed(source,rows)
        datasets.append((name,rows,seed,dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(data).hexdigest(),seed_method='known archived state' if name.startswith('ENA') else 'last two archived pivots known at seed boundary; observed opposite extreme')))
    rows=[dict(open_time=i*900000,close_time=(i+1)*900000-1,open=v,high=v,low=v,close=v) for i,v in enumerate((.4802,.43,.38))]
    seed=dict(pair=[.5818,.1302],direction=1,candidate=dict(price=D('.4802'),origin=0))
    datasets.append(('synthetic_user_prices',rows,seed,dict(note='Constructed numeric example, not historical OHLC; assumes .1302 is already confirmed')))
    rows,seed=shrinking_rows();datasets.append(('synthetic_shrinking',rows,seed,dict(note='Stress case, not market data')))
    all_stats={}
    for name,rows,seed,provenance in datasets:
        results,stats=compare(rows,seed)
        all_stats[name]=dict(candles=len(rows),first_open_ms=rows[0]['open_time'],last_open_ms=rows[-1]['open_time'],provenance=provenance,seed=seed,summary=stats)
        if name.startswith('ENA'):build_view(rows,results,stats,args.output/'ENAUSDT-15m-comparison.html','ENAUSDT 15m')
        if name=='synthetic_user_prices':build_view(rows,results,stats,args.output/'constructed-price-example.html','Constructed price example — not historical candles')
        (args.output/(name+'-events.json')).write_text(json.dumps({k:v['events'] for k,v in results.items()},separators=(',',':')))
        print(name,json.dumps(stats))
    (args.output/'summary.json').write_text(json.dumps(all_stats,indent=2,default=str)+'\n')

if __name__=='__main__':main()
