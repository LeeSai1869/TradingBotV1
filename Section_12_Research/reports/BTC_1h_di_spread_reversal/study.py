"""Causal, read-only BTC 1h DI-spread reversal event study and spot replays."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))

from collections import Counter
from datetime import datetime,timezone
import gzip,json,math,statistics,hashlib
from pathlib import Path

OUT=Path(__file__).parent
HOUR=3600000
FEE=.0004
SLIP=.0002
TARGET=.01

def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def utc(ms):return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()
def partition(row):
    year=datetime.fromtimestamp(row['open_time']/1000,timezone.utc).year
    return 'discovery_2017_2023' if year<=2023 else 'validation_2024' if year==2024 else 'holdout_2025_2026'
def spread(row):return row['features']['di_minus']-row['features']['di_plus']
def usable(row):
    f=row['features']
    return not f.get('measurement_gap') and all(finite(f.get(k)) for k in ('di_plus','di_minus','rsi')) and all(finite(row.get(k)) and row[k]>0 for k in ('open','high','low','close')) and row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high']
def signal(rows,i,threshold,*,rsi=False,at_peak=False,peak_only=False):
    if i<2 or i+1>=len(rows):return False
    a,b,c=rows[i-2:i+1]
    if not all(usable(r) for r in (a,b,c)) or a['close_time']+1!=b['open_time'] or b['close_time']+1!=c['open_time'] or c['close_time']+1!=rows[i+1]['open_time']:return False
    sa,sb,sc=(spread(r) for r in (a,b,c))
    # First decline from a local peak, including a flat-topped peak; no future maxima.
    if not (sb>=sa and sb>sc and sb>40 and (peak_only or sc>40)):return False
    f=(b if at_peak else c)['features']
    return f['di_minus']>threshold and (not rsi or f['rsi']<20)
def target_reference(entry_open,net=True,fee=FEE,slip=SLIP):
    entry_fill=entry_open*(1+slip)
    return entry_fill*(1+fee)*(1+TARGET)/((1-slip)*(1-fee)) if net else entry_open*(1+TARGET)
def net_return(reference,entry_open,fee=FEE,slip=SLIP):return (reference*(1-slip)*(1-fee)/(entry_open*(1+slip)*(1+fee))-1)*100

def _outcome(rows,i,*,horizon=24,stop=None,net=True,fee=FEE,slip=SLIP):
    """Entry next open; target-touch approximation, conservative stop-first ambiguity.

    A target-bar low may have occurred after exit, so adverse excursion includes it
    only as a conservative bound. Gaps terminate evaluation; never stitch across one.
    """
    entry_index=i+1;entry=rows[entry_index]['open'];target=target_reference(entry,net,fee,slip)
    stop_price=entry*(1-stop) if stop is not None else None
    trough=entry;max_up=entry;ambiguous=False;last_index=entry_index-1
    end=min(len(rows),entry_index+horizon) if horizon is not None else len(rows)
    for j in range(entry_index,end):
        row=rows[j]
        if j>entry_index and rows[j-1]['close_time']+1!=row['open_time']:
            return dict(status='GAP_CENSORED',exit_index=j-1,bars=j-entry_index,mae_pct=(trough/entry-1)*100,net_pct=None)
        if not all(finite(row.get(k)) and row[k]>0 for k in ('open','high','low','close')):
            return dict(status='GAP_CENSORED',exit_index=j-1,bars=j-entry_index,mae_pct=(trough/entry-1)*100,net_pct=None)
        last_index=j;trough=min(trough,row['low']);max_up=max(max_up,row['high'])
        stop_touch=stop_price is not None and row['low']<=stop_price
        target_touch=row['high']>=target
        if target_touch and row['open']>=target:
            return dict(status='TARGET',exit_index=j,bars=j-entry_index+1,mae_pct=(trough/entry-1)*100,net_pct=net_return(target,entry,fee,slip),ambiguous=False)
        if stop_touch:
            ambiguous=target_touch and row['open']>stop_price and row['open']<target
            price=min(stop_price,row['open'])
            return dict(status='STOP',exit_index=j,bars=j-entry_index+1,mae_pct=(trough/entry-1)*100,net_pct=net_return(price,entry,fee,slip),ambiguous=ambiguous)
        if target_touch:
            return dict(status='TARGET',exit_index=j,bars=j-entry_index+1,mae_pct=(trough/entry-1)*100,net_pct=net_return(target,entry,fee,slip),ambiguous=False)
    complete=horizon is not None and end-entry_index==horizon
    return dict(status='TIMEOUT' if complete else 'RIGHT_CENSORED',exit_index=last_index,bars=max(0,last_index-entry_index+1),mae_pct=(trough/entry-1)*100,mfe_pct=(max_up/entry-1)*100,net_pct=net_return(rows[last_index]['close'],entry,fee,slip) if complete else None)

def outcome(rows,i,*,horizon=24,**kwargs):
    result=_outcome(rows,i,horizon=horizon,**kwargs)
    # A known early hit in an incomplete end-of-dataset window must not enter
    # fixed-horizon hit rates while equally recent unresolved signals are omitted.
    result['full_horizon_available']=horizon is None or i+1+horizon<=len(rows)
    return result

def wilson(wins,n):
    if not n:return None
    z=1.96;p=wins/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;w=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(100*(c-w),2),round(100*(c+w),2)]
def summary(outcomes):
    complete=[r for r in outcomes if r['status'] not in ('RIGHT_CENSORED','GAP_CENSORED') and r.get('full_horizon_available',True)]
    wins=sum(r['status']=='TARGET' for r in complete);n=len(complete);returns=[r['net_pct'] for r in complete if r['net_pct'] is not None]
    return dict(signals=len(outcomes),evaluable=n,target_hits=wins,target_hit_pct=100*wins/n if n else None,hit_95pct_wilson=wilson(wins,n),incomplete_horizon_excluded=sum(not r.get('full_horizon_available',True) for r in outcomes),status_counts=dict(Counter(r['status'] for r in outcomes)),median_target_hours=statistics.median([r['bars'] for r in complete if r['status']=='TARGET']) if wins else None,mean_net_pct=statistics.mean(returns) if returns else None,median_net_pct=statistics.median(returns) if returns else None,worst_net_pct=min(returns) if returns else None,median_adverse_bound_pct=statistics.median(r['mae_pct'] for r in outcomes) if outcomes else None,worst_adverse_bound_pct=min((r['mae_pct'] for r in outcomes),default=None),ambiguous_stop_target_bars=sum(r.get('ambiguous',False) for r in outcomes))
def context(row,name):
    result=row['context'][name]
    return result['classification'] if result['data_quality'] in ('VALID','PARTIAL') else {}
def direction(row,name):
    c=context(row,name)
    return c.get('direction','UNKNOWN')
def candidates(rows,i):
    row=rows[i];prev=rows[i-1];f=row['features'];pf=prev['features'];rng=row['high']-row['low']
    atr=f.get('atr');cl=context(row,'TREND');reg=context(row,'REGIME')
    return dict(
        close_above_previous_high=row['close']>prev['high'],
        close_in_upper_30pct=rng>0 and (row['close']-row['low'])/rng>=.7,
        rsi_rising=finite(f['rsi']) and finite(pf['rsi']) and f['rsi']>pf['rsi'],di_plus_rising=finite(f['di_plus']) and finite(pf['di_plus']) and f['di_plus']>pf['di_plus'],
        relative_volume_ge_1_5=finite(f.get('relative_volume')) and f['relative_volume']>=1.5,
        natr_ge_1pct=finite(f.get('natr_pct')) and f['natr_pct']>=1,
        below_ema50_by_1atr=finite(atr) and atr>0 and finite(f.get('ema50')) and (f['ema50']-row['close'])/atr>=1,
        bearish_trend_weakening=cl.get('direction')=='BEARISH' and cl.get('persistence')=='DECLINING',
        not_trending_bearish_regime=not (reg.get('primary')=='TRENDING' and reg.get('direction')=='BEARISH') if reg else False)
def replay(rows,indices,*,horizon=24,stop=None,fee=FEE,slip=SLIP):
    outcomes=[];last_exit=-1;equity=peak=1.;drawdown=0.;skipped=0
    for i in indices:
        if i+1<=last_exit:skipped+=1;continue
        result=outcome(rows,i,horizon=horizon,stop=stop,fee=fee,slip=slip);result.update(entry_open=rows[i+1]['open'],entry_time=rows[i+1]['open_time']);outcomes.append(result);last_exit=result['exit_index']
        if result['net_pct'] is not None:
            equity*=1+result['net_pct']/100;peak=max(peak,equity);drawdown=min(drawdown,(equity/peak-1)*100)
    return dict(**summary(outcomes),overlap_skipped=skipped,target_pct_all_started=100*sum(r['status']=='TARGET' for r in outcomes)/len(outcomes) if outcomes else None,max_holding_hours=max((r['bars'] for r in outcomes),default=None),longest_holds=[dict(status=r['status'],hours=r['bars'],entry_utc=utc(r['entry_time']),last_observed_utc=utc(rows[r['exit_index']]['close_time']),adverse_bound_pct=r['mae_pct'],net_pct=r['net_pct']) for r in sorted(outcomes,key=lambda r:r['bars'],reverse=True)[:3]],closed_trade_compounded_pct=(equity-1)*100,closed_equity_max_drawdown_pct=drawdown,account_return_valid=not any(r['status'] in ('RIGHT_CENSORED','GAP_CENSORED') for r in outcomes),censored_positions=[dict(status=r['status'],entry_utc=utc(r['entry_time']),bars=r['bars'],last_known_mtm_pct=net_return(rows[r['exit_index']]['close'],r['entry_open'],fee,slip)) for r in outcomes if r['status'] in ('RIGHT_CENSORED','GAP_CENSORED')])

def analyze(packet):
    rows=packet['rows'];result=dict(version='btc-di-spread-reversal-study-v1',source_signature=packet['source_signature'],observed_as_of=packet['observed_as_of'],coverage=dict(candles=len(rows),first_utc=utc(rows[0]['open_time']),last_closed_utc=utc(rows[-1]['close_time'])),costs=dict(fee_bps_per_side=FEE*10000,slippage_bps_per_side=SLIP*10000,net_target_pct=1,required_price_rise_pct=(target_reference(100)/100-1)*100,net_after_gross_1pct=net_return(101,100)),definition='Signal at first closed bearish-spread drop after local peak (plateaus accepted), peak and signal spread >40; DI- threshold at signal, optional RSI<20 at signal. Buy next open. Missing/gapped input is ineligible. No pivot-low entry. No production rule changes.',variants={},bearish_filter_tests={},threshold_timing_sensitivity={})
    def split_member(i,split):
        # Purge forward outcome windows that cross the chronological split.
        return partition(rows[i])==split and i+24<len(rows) and partition(rows[i+24])==split
    for threshold in (40,45,50):
        for rsi in (False,True):
            name=f'di_minus_gt_{threshold}'+('_rsi_lt_20' if rsi else '')
            indices=[i for i in range(2,len(rows)-1) if signal(rows,i,threshold,rsi=rsi)]
            outcomes={h:[outcome(rows,i,horizon=h) for i in indices] for h in (6,12,24,48,72,168)}
            variant=dict(raw_signal_count=len(indices),horizons={str(h):summary(v) for h,v in outcomes.items()},by_split={},by_trend={},by_regime={},by_confirmed_trend={},by_trending_bearish_regime={},single_position={},events=[])
            for split in ('discovery_2017_2023','validation_2024','holdout_2025_2026'):
                selected=[i for i in indices if split_member(i,split)]
                variant['by_split'][split]=summary([outcome(rows,i) for i in selected])
            for engine,dest in [('TREND','by_trend'),('REGIME','by_regime')]:
                for label in ('BULLISH','BEARISH','NEUTRAL','UNKNOWN'):
                    selected=[i for i in indices if direction(rows[i],engine)==label]
                    variant[dest][label]=summary([outcome(rows,i) for i in selected])
            for label in ('BULLISH','BEARISH','NEUTRAL','UNKNOWN'):
                selected=[i for i in indices if (direction(rows[i],'TREND') if rows[i]['context']['TREND']['confirmation']['status']=='CONFIRMED' else 'UNKNOWN')==label]
                variant['by_confirmed_trend'][label]=summary([outcome(rows,i) for i in selected])
            for label in ('TRENDING_BEARISH','OTHER_KNOWN','UNKNOWN'):
                def bucket(i):
                    r=context(rows[i],'REGIME')
                    return 'TRENDING_BEARISH' if r.get('primary')=='TRENDING' and r.get('direction')=='BEARISH' else 'OTHER_KNOWN' if r else 'UNKNOWN'
                selected=[i for i in indices if bucket(i)==label]
                variant['by_trending_bearish_regime'][label]=summary([outcome(rows,i) for i in selected])
            for label,stop in [('no_stop',None),('stop_0_5pct',.005),('stop_1pct',.01),('stop_2pct',.02)]:variant['single_position'][label]=replay(rows,indices,stop=stop)
            variant['single_position']['no_time_limit_no_stop']=replay(rows,indices,horizon=None)
            variant['gross_target_24h_event_study']=summary([outcome(rows,i,net=False) for i in indices])
            variant['single_position']['fee10bps_slip2bps_24h']=replay(rows,indices,fee=.001)
            for i,o in zip(indices,outcomes[24]):
                event=dict(signal_index=i,signal_time=rows[i]['open_time'],signal_utc=utc(rows[i]['open_time']),entry_utc=utc(rows[i+1]['open_time']),split=partition(rows[i]),di_minus=rows[i]['features']['di_minus'],spread=spread(rows[i]),peak_spread=spread(rows[i-1]),rsi=rows[i]['features']['rsi'],entry_open=rows[i+1]['open'],target_reference=target_reference(rows[i+1]['open']),trend=context(rows[i],'TREND'),regime=context(rows[i],'REGIME'),outcome_24h=o,filters=candidates(rows,i))
                variant['events'].append(event)
            result['variants'][name]=variant
            result['threshold_timing_sensitivity'][name]={}
            for label,kwargs in [('thresholds_at_peak',dict(at_peak=True)),('spread_above40_at_peak_only',dict(peak_only=True)),('thresholds_at_peak_spread_peak_only',dict(at_peak=True,peak_only=True))]:
                selected=[i for i in range(2,len(rows)-1) if signal(rows,i,threshold,rsi=rsi,**kwargs)]
                result['threshold_timing_sensitivity'][name][label]=summary([outcome(rows,i) for i in selected])
            bearish=[i for i in indices if direction(rows[i],'TREND')=='BEARISH']
            tests={}
            for filter_name in ['BASELINE']+list(candidates(rows,2)):
                group=bearish if filter_name=='BASELINE' else [i for i in bearish if candidates(rows,i)[filter_name]]
                tests[filter_name]={split:summary([outcome(rows,i) for i in group if split=='all' or split_member(i,split)]) for split in ('all','discovery_2017_2023','validation_2024','holdout_2025_2026')}
            result['bearish_filter_tests'][name]=Section_13_Development/tests
    result['latest_candles']=[dict(time_utc=utc(r['open_time']),close=r['close'],di_minus=r['features']['di_minus'],spread=spread(r),rsi=r['features']['rsi'],trend=context(r,'TREND'),regime=context(r,'REGIME')) for r in rows[-5:]]
    result['limitations']=['Hourly OHLC target touches approximate a standing exit; no order queue/volume fill guarantee. A gap above target receives only target price.','Signals within overlapping market episodes are correlated; event-study hit rates are not independent trades. Single-position replays skip overlaps.','No-stop eventual-hit rates include potentially very long capital lockups and right-censored trades. Timeouts are marked to market at horizon close; this is an explicit comparison exit, not a user-selected stop.','Adverse excursions include the entire target/stop hourly candle and are conservative bounds; intrabar order is unknown. If target and stop both touch, stop is applied first.','Current Section 5 definitions are replayed causally offline, with original Section 4 structure event lineage; this is reconstructed historical availability, not original live publication.','2025-2026 is a chronological holdout, not prospective validation: the hypothesis was motivated by already viewed charts. Additional filter comparisons are exploratory and not selected using holdout performance.','Observed liquidity feed is Binance USDT perpetual depth, not spot depth; missing historical observations are not fabricated or used as a historical buy gate.','Fees/slippage are explicit scenarios, not a claim about the actual account commission rate.']
    return result

if __name__=='__main__':
    packet=json.loads(gzip.decompress((OUT/'source.json.gz').read_bytes()));result=analyze(packet)
    (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    for name,v in result['variants'].items():print(name,json.dumps(v['horizons']['24']),flush=True)
