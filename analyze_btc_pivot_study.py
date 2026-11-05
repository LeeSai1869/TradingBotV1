"""Reproduce findings from uploaded five-timeframe pivot studies; no market DBs."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics

FRAMES=('15m','30m','1h','4h','1d')
STEPS={'15m':900000,'30m':1800000,'1h':3600000,'4h':14400000,'1d':86400000}
FIELDS=('atr_pct_of_close','relative_volume','range_in_atr','ema50_distance_pct','ema200_distance_pct',
    'distance_to_swing_high_pct','distance_to_swing_low_pct','adx','rsi','di_plus','di_minus','di_absolute_spread',
    'di_plus_dominant','di_plus_peak_confirmed_at_close','di_minus_peak_confirmed_at_close',
    'lower_wick_fraction','upper_wick_fraction','close_position','efficiency_ratio')


def groups_for(packet,name):
    """Recover the original exporter's ATR fraction/percent name collision explicitly."""
    source=name
    if name=='atr_pct_of_close' and name not in packet['features']:source='atr_percent'
    rows=packet['features'].get(source,[]);found={};collisions=0
    for row in rows:
        key=(row['side'],row['outcome'],row['year'])
        if key in found:
            previous=found[key];collisions+=1
            if source!='atr_percent' or previous['count']!=row['count']:raise ValueError('Unexpected duplicate feature groups')
            for metric in ('mean','stddev','minimum','maximum'):
                for a,b in zip(previous[metric],row[metric]):
                    if (a is None)!=(b is None) or a is not None and not math.isclose(a*100,b,rel_tol=1e-8,abs_tol=1e-9):
                        raise ValueError('ATR collision does not match documented 100x units')
        found[key]=row
    if name=='atr_pct_of_close' and source=='atr_percent' and rows and not collisions:
        raise ValueError('Ambiguous legacy ATR units; no documented paired export to recover')
    return list(found.values()),collisions


def effect_profile(rows,side,idx):
    groups={r['outcome']:r for r in rows if r['side']==side and r['year']=='ALL'}
    hit,non=groups.get('HIT'),groups.get('NO_HIT');annual={}
    for row in rows:
        if row['side']==side and row['year']!='ALL':annual.setdefault(row['year'],{})[row['outcome']]=row
    positive=negative=eligible=0;effects=[]
    for year,g in annual.items():
        h,n=g.get('HIT'),g.get('NO_HIT')
        if not h or not n or min(h['count'][idx],n['count'][idx])<30:continue
        eligible+=1
        delta=h['mean'][idx]-n['mean'][idx];positive+=delta>0;negative+=delta<0
        sd=math.sqrt((h['stddev'][idx]**2+n['stddev'][idx]**2)/2)
        if sd>0:effects.append(delta/sd)
    return dict(hit_mean=hit['mean'][idx] if hit else None,nonhit_mean=non['mean'][idx] if non else None,
        hit_available=hit['count'][idx] if hit else 0,nonhit_available=non['count'][idx] if non else 0,
        eligible_years=eligible,positive_years=positive,negative_years=negative,
        median_within_year_standardized_difference=statistics.median(effects) if effects else None)


def analyze(paths,progress=None):
    result=dict(version='btc-pivot-findings-v1',frames={},interpretation='Retrospective pivot-conditioned descriptive comparisons, not executable profits, an early recognition precision/recall study, a calibrated probability or proof of causal/predictive performance. Only predefined summary features are used in the narrative; all numeric effects are exploratory. Within-year comparisons do not remove volatility confounding. Positive offsets are later evidence. No production rules changed.')
    for frame in FRAMES:
        cohort=paths/f'BTCUSDT_{frame}_all-history_1pct_pivots_v1.json.gz';features=paths/f'BTCUSDT_{frame}_all-history_1pct_features_v1.json.gz'
        data=cohort.read_bytes();p=json.loads(gzip.decompress(data))
        if p['symbol']!='BTCUSDT' or p['timeframe']!=frame or p['config']['threshold_pct']!=1 or p['config']['horizon_bars'] is not None:raise ValueError('Incompatible cohort')
        entry=dict(pivots=len(p['cases']),coverage=p['coverage'],cutoff=p['observed_as_of'],source_id=p['source_id'],warnings=p['warnings'],
                   source_files={cohort.name:hashlib.sha256(data).hexdigest()},sides={})
        for side in ('BUY_SIDE','SELL_SIDE'):
            cases=[c for c in p['cases'] if c['side']==side];hits=[c for c in cases if c['origin']['status']=='HIT'];nonhits=[c for c in cases if c['origin']['status']=='NO_HIT']
            entry['sides'][side]=dict(n=len(cases),hits=len(hits),nonhits=len(nonhits),censored=len(cases)-len(hits)-len(nonhits),
                origin_hit_rate_pct=100*len(hits)/(len(hits)+len(nonhits)) if hits or nonhits else None,
                hits_by_confirmation=sum(c['origin_hit_by_confirmation'] for c in hits),
                hit_already_by_confirmation_pct=100*sum(c['origin_hit_by_confirmation'] for c in hits)/len(hits) if hits else None,
                median_first_hit_following_bar=statistics.median(c['origin']['first_hit']['bars'] for c in hits) if hits else None,
                median_confirmation_delay_intervals=statistics.median((c['pivot']['known_time']-c['pivot']['origin_time'])/STEPS[frame] for c in cases) if cases else None,
                profiles={})
        del p,data
        data=features.read_bytes();p=json.loads(gzip.decompress(data));entry['source_files'][features.name]=hashlib.sha256(data).hexdigest();del data
        if p['source_id']!=entry['source_id'] or p['pivots']!=entry['pivots'] or p['threshold_pct']!=1:raise ValueError('Feature cohort mismatch')
        entry.update(offsets=p['offsets'],numeric_feature_names=len(p['features']),missing_exact_offset_rows=p['missing_exact_offset_rows'],timing=p['timing'],
            engine_source_status=p['engine_context']['source_status'],categorical_at_origin={key:[{k:v for k,v in g.items() if k!='counts'}|dict(counts=g['counts'][p['offsets'].index(0)]) for g in groups] for key,groups in p['categorical_features'].items()})
        coverage=defaultdict(Counter)
        for g in p['engine_context']['groups']:
            key=f"{g['stage']}:{g['timeframe']}:{g['engine']}";coverage[key]['total']+=g['count'];coverage[key]['classification_present']+=g['count'] if g.get('classification') else 0
        entry['engine_coverage']={k:dict(v) for k,v in coverage.items()}
        entry['exploratory_effects']=[];entry['unit_recovery']={}
        for name in dict.fromkeys([*FIELDS,*(n for n in p['features'] if n!='atr_percent')]):
            rows,duplicates=groups_for(p,name)
            if duplicates:entry['unit_recovery'][name]=dict(duplicate_groups_resolved=duplicates,basis='Use derived 100*ATR/price groups; matching counts and 100x scale verified')
            for side in ('BUY_SIDE','SELL_SIDE'):
                if name in FIELDS:
                    entry['sides'][side]['profiles'][name]=dict(groups={r['outcome']:{key:r[key] for key in ('pivots','count','mean','stddev')} for r in rows if r['side']==side and r['year']=='ALL'},
                        offsets={str(o):effect_profile(rows,side,p['offsets'].index(o)) for o in (-3,-2,-1,0,1,2,3)})
                for o in (-1,0):entry['exploratory_effects'].append(dict(feature=name,side=side,offset=o,**effect_profile(rows,side,p['offsets'].index(o))))
        entry['raw_pivot_price_checks']=dict(checked=sum(g['pivots'] for g in p['timing']),matching=sum(g['origin_price_matches_raw'] for g in p['timing']))
        if entry['raw_pivot_price_checks']['matching']!=entry['pivots']:raise ValueError('Raw pivot price mismatch requires inspection')
        result['frames'][frame]=entry
        if progress:progress(frame,entry['pivots'])
        del p
    result['total_pivots']=sum(e['pivots'] for e in result['frames'].values())
    return result


def plots(result,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    x=np.arange(len(FRAMES));fig,axes=plt.subplots(1,2,figsize=(13,5))
    for side,color,shift in (('BUY_SIDE','#247ab5',-.18),('SELL_SIDE','#d87927',.18)):
        axes[0].bar(x+shift,[result['frames'][f]['sides'][side]['origin_hit_rate_pct'] for f in FRAMES],.36,label=side,color=color)
        axes[1].bar(x+shift,[result['frames'][f]['sides'][side]['hit_already_by_confirmation_pct'] for f in FRAMES],.36,label=side,color=color)
    for ax in axes:ax.set_xticks(x,FRAMES);ax.set_ylim(0,105);ax.legend();ax.grid(axis='y',alpha=.2)
    axes[0].set(title='1% reached from retrospective pivot extreme',ylabel='Resolved pivot windows (%)')
    axes[1].set(title='Successful moves already at 1% by formal confirmation',ylabel='Origin-HIT pivots (%)')
    fig.suptitle('Not trading win rates: pivots were selected with hindsight; daily has no complete non-hit controls',fontsize=11)
    fig.tight_layout();fig.savefig(out/'benchmark_and_confirmation.png',dpi=160);plt.close(fig)
    frame=result['frames']['1h'];fig,axes=plt.subplots(3,2,figsize=(13,10),sharex=True)
    for col,side in enumerate(('BUY_SIDE','SELL_SIDE')):
        for row,name in enumerate(('atr_pct_of_close','relative_volume','di_minus' if side=='BUY_SIDE' else 'di_plus')):
            for outcome,color in (('HIT','#247ab5'),('NO_HIT','#d87927')):
                g=frame['sides'][side]['profiles'][name]['groups'][outcome]
                xx=[o for o in frame['offsets'] if -6<=o<=6];yy=[g['mean'][frame['offsets'].index(o)] for o in xx]
                axes[row,col].plot(xx,yy,label=outcome,color=color,linewidth=2)
            axes[row,col].axvline(0,color='#887400',linestyle='--');axes[row,col].set_ylabel(name);axes[row,col].grid(alpha=.2)
        axes[0,col].set_title(side+' · BTC 1h');axes[0,col].legend();axes[2,col].set_xlabel('Candle offset from actual pivot origin')
    fig.suptitle('Group means: offset 0 uses its close; positive offsets are later evidence, not a past prediction',fontsize=11)
    fig.tight_layout();fig.savefig(out/'one_hour_pivot_profiles.png',dpi=160);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reports-dir',type=Path,default=Path('research_reports/BTC_1pct'));parser.add_argument('--output-dir',type=Path,default=Path('research_reports/BTC_1pct_findings'));parser.add_argument('--no-plots',action='store_true');args=parser.parse_args()
    packet=analyze(args.reports_dir,progress=lambda frame,n:print(frame,n,'pivots analyzed',flush=True));args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'statistics.json.gz').write_bytes(gzip.compress((json.dumps(packet,separators=(',',':'),allow_nan=False)+'\n').encode(),mtime=0))
    if not args.no_plots:plots(packet,args.output_dir)
    print('Total:',packet['total_pivots'],'· saved to',args.output_dir)

if __name__=='__main__':main()
