"""Reproduce descriptive statistics/figures from an exported pivot report only."""
import argparse
import collections
import csv
from datetime import datetime,timezone
import gzip
import json
import math
from pathlib import Path
import statistics


def numeric(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def median(values):
    valid=[v for v in values if numeric(v)]
    return statistics.median(valid) if valid else None


def utc(stamp):return datetime.fromtimestamp(stamp/1000,timezone.utc).isoformat()


def analyze(report):
    if report.get('version')!='pivot-moves-v1':raise ValueError('Expected pivot-moves-v1 report')
    cases=report['cases'];lookup={c['id']:c for c in cases};profiles=[]
    if len(cases)!=report['summary']['pivots']:raise ValueError('Case count differs from exported summary')
    step={'1m':60000,'5m':300000,'15m':900000,'30m':1800000,'1h':3600000}[report['timeframe']]
    sides={};years=[]
    for side in ('BUY_SIDE','SELL_SIDE'):
        group=[c for c in cases if c['side']==side];hits=[c for c in group if c['origin']['status']=='HIT'];known=[c for c in group if c['after_known']['status']=='HIT']
        sides[side]=dict(pivots=len(group),origin_hits=len(hits),after_known_hits=len(known),
            hits_by_confirmation=sum(c['origin_hit_by_confirmation'] for c in hits),
            origin_hit_rate_pct=100*len(hits)/len(group) if group else None,
            after_known_status_counts=dict(collections.Counter(c['after_known']['status'] for c in group)),
            median_leg_bars=median((c['next_opposite']['origin_time']-c['pivot']['origin_time'])/step for c in group if c['next_opposite']),
            median_origin_hit_bars=median(c['origin']['first_hit']['bars'] for c in hits),
            median_confirmation_delay_bars=median((c['pivot']['known_time']-c['pivot']['origin_time'])/step for c in group))
        exported=report['summary'].get('by_side',{}).get(side)
        if exported and any(sides[side][key]!=exported[key] for key in ('pivots','origin_hits','after_known_hits','hits_by_confirmation')):
            raise ValueError('Side counts differ from exported summary')
        for year in sorted({utc(c['pivot']['origin_time'])[:4] for c in group}):
            cohort=[c for c in group if utc(c['pivot']['origin_time']).startswith(year)]
            years.append(dict(year=year,side=side,pivots=len(cohort),origin_hits=sum(c['origin']['status']=='HIT' for c in cohort),after_known_hits=sum(c['after_known']['status']=='HIT' for c in cohort)))
    for id,context in report.get('contexts',{}).items():
        case=lookup[id];origin=case['pivot']['origin_time'];bars={r['client']['open_time']:r for r in context['bars']};r=bars.get(origin);prev=bars.get(origin-step)
        if not r:continue
        f=r['features'];side=case['side'];pressure='di_minus' if side=='BUY_SIDE' else 'di_plus';opposite='di_plus' if side=='BUY_SIDE' else 'di_minus'
        features=lambda record,key:record['features'].get(key) if record else None
        peaks=[];valid_peak_windows=0
        for offset in range(-2,1):
            values=[features(bars.get(origin+(offset+i)*step),pressure) for i in (-1,0,1)]
            if all(numeric(v) for v in values):
                valid_peak_windows+=1
                if values[0]<values[1]>values[2]:peaks.append(offset)
        atr=f.get('atr');close=r['client']['close'];di=[f.get(pressure),f.get(opposite)]
        profiles.append(dict(id=id,date=utc(origin),side=side,outcome=case['origin']['status'],
            atr_pct=100*atr/close if numeric(atr) and close>0 else None,
            rsi=f.get('rsi'),adx=f.get('adx'),relative_volume=f.get('relative_volume'),
            pressure=di[0],counterpart=di[1],spread=abs(di[0]-di[1]) if all(numeric(v) for v in di) else None,
            pressure_dominant=di[0]>di[1] if all(numeric(v) for v in di) else None,
            pressure_falling=f[pressure]<features(prev,pressure) if numeric(f.get(pressure)) and numeric(features(prev,pressure)) else None,
            candle_range_atr=(r['client']['high']-r['client']['low'])/atr if numeric(atr) and atr>0 else None,
            candidate_same_side=f.get('candidate_pivot')==(-1 if side=='BUY_SIDE' else 1),
            pressure_peak_near_origin=True if peaks else False if valid_peak_windows==3 else None,pressure_peak_offsets=peaks,current_structure=f.get('current_structure')))
    sample_groups=[]
    for side in ('BUY_SIDE','SELL_SIDE'):
        for outcome in ('HIT','NO_HIT'):
            group=[p for p in profiles if p['side']==side and p['outcome']==outcome]
            sample_groups.append(dict(side=side,outcome=outcome,n=len(group),
                medians={key:median(p[key] for p in group) for key in ('atr_pct','rsi','adx','relative_volume','spread','candle_range_atr')},
                counts={key:dict(true=sum(p[key] is True for p in group),available=sum(p[key] is not None for p in group)) for key in ('pressure_dominant','pressure_falling','candidate_same_side','pressure_peak_near_origin')}))
    rows=[r for c in report.get('contexts',{}).values() for r in c['bars']]
    pivot_price_checks=[]
    for id,packet in report.get('contexts',{}).items():
        case=lookup[id];record=next((r for r in packet['bars'] if r['client']['open_time']==case['pivot']['origin_time']),None)
        if record:pivot_price_checks.append(abs(record['client']['low' if case['side']=='BUY_SIDE' else 'high']-case['pivot']['price'])<1e-8)
    quality=dict(pivot_prices_matching_raw_candle=sum(pivot_price_checks),pivot_price_checks=len(pivot_price_checks),context_cases=len(report.get('contexts',{})),exported_context_rows=len(rows),
        unique_context_rows=len({r['client']['open_time'] for r in rows}),
        current_structure_counts=dict(collections.Counter(str(r['features'].get('current_structure')) for r in rows)),
        bearish_structure_active_counts=dict(collections.Counter(str(r['features'].get('bearish_structure_active')) for r in rows)),
        sample_year_counts={outcome:dict(collections.Counter(p['date'][:4] for p in profiles if p['outcome']==outcome)) for outcome in ('HIT','NO_HIT')})
    return dict(source_version=report['version'],source_id=report['source_id'],coverage=report['coverage'],sides=sides,years=years,sample_groups=sample_groups,quality=quality,profiles=profiles,
                interpretation='Full-cohort outcome/timing statistics; feature comparisons use only exported descriptive examples, are not year/volatility matched, and are not causal or predictive validation.')


def figures(report,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    lookup={c['id']:c for c in report['cases']};step={'1m':60000,'5m':300000,'15m':900000,'30m':1800000,'1h':3600000}[report['timeframe']]
    pairs=[('buy_comparison.png',['037049bebbe7','75608d42c90d']),('sell_comparison.png',['363d278bf4f5','a82bc1f6046f'])]
    for name,prefixes in pairs:
        ids=[next((id for id in report.get('contexts',{}) if id.startswith(prefix)),None) for prefix in prefixes]
        if any(id is None for id in ids):
            (out/name).unlink(missing_ok=True)
            continue
        fig,axes=plt.subplots(4,2,figsize=(16,12),sharex='col',gridspec_kw=dict(height_ratios=[3,2,2,1.5]))
        for col,id in enumerate(ids):
            case=lookup[id];context=report['contexts'][id];pivot=case['pivot'];origin=pivot['origin_time'];bars=context['bars'];x=[(r['client']['open_time']-origin)/step for r in bars]
            for pos,record in zip(x,bars):
                b=record['client'];color='#18876b' if b['close']>=b['open'] else '#c44b53'
                axes[0,col].vlines(pos,b['low'],b['high'],color=color,linewidth=1)
                axes[0,col].add_patch(Rectangle((pos-.32,min(b['open'],b['close'])),.64,max(abs(b['close']-b['open']),pivot['price']*.000005),facecolor=color,edgecolor=color))
            target=pivot['price']*(1+(.02 if case['side']=='BUY_SIDE' else -.02))
            axes[0,col].axhline(target,color='#178ca4',linestyle=':',label='2% from retrospective pivot')
            axes[0,col].set_title(f"{utc(origin)[:16]} UTC · {case['side']}\n{case['origin']['status']}: observed max {case['origin']['max_favorable_pct']:.2f}%"+(' · partial swing' if not case['origin']['complete'] else ''),fontsize=11)
            for key,color in [('di_plus','#18876b'),('di_minus','#c44b53')]:axes[1,col].plot(x,[r['features'].get(key) for r in bars],label=key,color=color)
            axes[1,col].plot(x,[abs(r['features']['di_plus']-r['features']['di_minus']) if numeric(r['features'].get('di_plus')) and numeric(r['features'].get('di_minus')) else None for r in bars],color='#6954a1',label='absolute spread',linestyle='--')
            for key,color in [('rsi','#247aaf'),('adx','#bd8121')]:axes[2,col].plot(x,[r['features'].get(key) for r in bars],label=key,color=color)
            axes[2,col].axhline(30,color='#aaa',linewidth=.6,linestyle=':');axes[2,col].axhline(70,color='#aaa',linewidth=.6,linestyle=':')
            axes[3,col].bar(x,[r['features'].get('relative_volume') if numeric(r['features'].get('relative_volume')) else float('nan') for r in bars],color='#728b9c',width=.65,label='Relative volume (missing omitted)')
            for ax in axes[:,col]:
                ax.axvline(0,color='#8155a6',linestyle='--',linewidth=1,label='Pivot origin' if ax is axes[0,col] else None)
                ax.axvline((pivot['known_time']-origin)/step,color='#c88914',linestyle='--',linewidth=1,label='Known at close' if ax is axes[0,col] else None)
                endpoint=case['next_opposite']['origin_time'] if case['next_opposite'] else report['observed_as_of']
                end=(endpoint-origin)/step
                ax.axvspan(0,min(end,max(x)),color='#159b8b',alpha=.06)
                if min(x)<=end<=max(x):ax.axvline(end,color='#555',linestyle=':',label='Swing endpoint' if ax is axes[0,col] else None)
                ax.grid(alpha=.18);ax.legend(loc='upper left',fontsize=7)
            axes[0,col].set_ylabel('BTC price (USDT)');axes[1,col].set_ylabel('DI points');axes[2,col].set_ylabel('RSI / ADX');axes[3,col].set_ylabel('RVOL');axes[3,col].set_xlabel(report['timeframe']+' candles relative to pivot (0); shaded region is measured swing')
        fig.suptitle('Historical examples, not trading rules. Titles show full-window maxima; plots show the exported context only.',fontsize=12)
        fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(out/name,dpi=150);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--no-plots',action='store_true');args=parser.parse_args()
    report=json.loads(gzip.decompress(args.report.read_bytes()) if args.report.suffix=='.gz' else args.report.read_bytes());result=analyze(report)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'statistics.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    with (args.output_dir/'context_profiles.csv').open('w',newline='') as stream:
        rows=result['profiles'];writer=csv.DictWriter(stream,fieldnames=list(rows[0]) if rows else ['id']);writer.writeheader();writer.writerows(rows)
    if not args.no_plots:figures(report,args.output_dir)
    print(json.dumps(dict(sides=result['sides'],quality=result['quality']),indent=2))

if __name__=='__main__':main()
