"""Fixed bearish target; unchanged bullish trail; causal entry execution checks."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))

from collections import Counter
from dataclasses import dataclass,asdict
import gzip,hashlib,json,math,sqlite3
from pathlib import Path
from Section_12_Research.reports.BTC_1h_di_spread_trailing_v2 import replay as base,intrabar_5m as intra
from Section_12_Research.reports.BTC_1h_bear_target_breakouts_v3 import features

OUT=Path(__file__).parent
V2=OUT.parent/'BTC_1h_di_spread_trailing_v2'

@dataclass(frozen=True)
class Policy(base.Policy):
    bearish_exit:str='fixed_target'
    bearish_target_basis:str='net_1pct'
    risk:str='net_0_5pct'


def freeze_volumes(bars):
    path=OUT/'five_minute_volumes.json.gz'
    if path.exists():
        packet=json.loads(gzip.decompress(path.read_bytes()))
        if packet['count']!=len(bars) or packet['first']!=bars[0][0] or packet['last']!=bars[-1][0]:raise ValueError('Volume/source alignment mismatch')
        return packet['values']
    from Section_1_Global_Core.memory_storage.Storage import klines_store
    c=sqlite3.connect(klines_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1);lookup={};after=-1
    try:
        while True:
            rows=c.execute('SELECT open_time,volume FROM klines WHERE symbol=? AND interval=? AND open_time>? AND close_time<=? ORDER BY open_time LIMIT 8192',('BTCUSDT','5m',after,bars[-1][1])).fetchall()
            if not rows:break
            lookup.update(rows);after=rows[-1][0]
    finally:c.close()
    values=[lookup.get(b[0]) for b in bars];packet=dict(count=len(bars),first=bars[0][0],last=bars[-1][0],values=values)
    path.write_bytes(gzip.compress(json.dumps(packet,separators=(',',':'),allow_nan=False).encode(),compresslevel=1,mtime=0));return values


def entry_from(s,k,bars,context,feature_name):
    if k+1>=len(bars) or bars[k+1][0]!=bars[k][1]+1:return None
    known=bars[k][1]+1;direction,_=context.at(known)
    if direction not in ('BULLISH','BEARISH'):return None
    return dict(signal_time=bars[k][0],known_time=known,entry_time=known,entry_open=bars[k+1][2],entry_regime=direction,hour_index=s['hour_index'],setup_known_time=s['known_time'],setup_di_minus=s.get('peak_di_minus'),setup_rsi=s.get('preview_rsi'),feature=feature_name,bar_index=k)


def candidates(signals,bars,observations,context,threshold,rsi_mode,method,gate,lookup=None):
    if lookup is None:lookup={b[0]:i for i,b in enumerate(bars)}
    out=[];reasons=Counter()
    for s in signals:
        if s['method']!=method or s['peak_di_minus']<=threshold:continue
        if rsi_mode=='signal' and s['preview_rsi']>=20:continue
        reasons['setups']+=1;k=lookup[s['signal_time']];f=observations[k]
        if not f.ready:reasons['context_not_ready']+=1;continue
        chosen=None
        if gate=='immediate':chosen=k
        elif gate=='avoid_recent_crash':
            if not f.crash_recent:chosen=k
            else:reasons['crash_veto']+=1
        elif gate=='avoid_unrecovered_crash':
            if not f.crash_unrecovered:chosen=k
            else:reasons['crash_veto']+=1
        else:
            feature={'wait_micro_reclaim':'micro_reclaim','wait_range_low_reclaim':'range_low_reclaim','wait_volume_breakout':'breakout_up'}[gate]
            for j in range(k,min(len(bars)-1,k+7)):
                if bars[j][0]!=bars[k][0]+(j-k)*features.STEP:reasons['confirmation_gap']+=1;break
                f=observations[j]
                if f.crash:reasons['new_crash_cancelled']+=1;break
                if f.ready and f[feature] and not f.crash_recent:chosen=j;break
            if chosen is None:reasons['no_confirmation']+=1
        if chosen is not None:
            entry=entry_from(s,chosen,bars,context,gate)
            if entry:out.append(entry)
            else:reasons['neutral_unknown_or_missing_next_open']+=1
    unique={e['entry_time']:e for e in out};reasons['duplicate_entry_times']=len(out)-len(unique)
    return sorted(unique.values(),key=lambda e:e['entry_time']),dict(reasons)


def breakout_candidates(bars,observations,context,hours,kind):
    hour_index={r['open_time']:i for i,r in enumerate(hours)};out=[]
    for k,f in enumerate(observations[:-1]):
        if not f.ready or not f[kind] or f.crash_recent:continue
        known=bars[k][1]+1;direction,plus=context.at(known)
        if direction!='BULLISH' or not base.finite(plus):continue
        i=hour_index.get(bars[k][0]//base.HOUR*base.HOUR)
        if i is None:continue
        s=dict(hour_index=i,known_time=known)
        entry=entry_from(s,k,bars,context,kind)
        if entry:out.append(entry)
    return out


def run_portfolio(entries,hours,execution,context,policy,cache,order):
    taken=[];ids=[];blocked=-1;overlap=0;unpriced=0
    for e in entries:
        if e['entry_time']<blocked:overlap+=1;continue
        key=(e['entry_time'],policy)
        if key not in cache:
            override={k:e[k] for k in ('signal_time','entry_time','entry_open','entry_regime')}
            cache[key]=base.paired_trade(hours,min(e['hour_index'],len(hours)-2),execution,context,policy,override)
        tr=next(x for x in cache[key] if x['order']==order)
        if tr['status']=='ENTRY_PRICE_MISMATCH':unpriced+=1;continue
        taken.append(tr);ids.append(e['entry_time']);blocked=tr['exit_time_upper'] if tr['status']=='CLOSED' else math.inf
    result=base.portfolio(taken);result.update(overlap_skipped=overlap,unpriced_entries_skipped=unpriced,accepted_entry_times=ids)
    if unpriced:result['account_return_complete']=False
    periods={name:base.summarize([t for t in taken if (t['entry_time']<1704067200000 if name=='2017_2023' else 1704067200000<=t['entry_time']<1735689600000 if name=='2024' else t['entry_time']>=1735689600000)]) for name in ('2017_2023','2024','2025_2026')}
    result['periods']=periods
    return result


def reference_barrier(entry,policy,execution,tf):
    """Independent first-hit oracle for an entry-frozen bearish fixed target.
    No trailing code, per-point path or production classifier is reused here.
    """
    fill=entry['entry_open']*(1+policy.slip)
    hard=fill*(1+policy.fee)*.995/((1-policy.slip)*(1-policy.fee)) if policy.risk=='net_0_5pct' else fill*.995
    target=fill*(1+policy.fee)*1.01/((1-policy.slip)*(1-policy.fee)) if policy.activation=='net_1pct' else fill*1.01
    for t,end,o,h,l,c in execution.bars(entry['entry_time'],tf):
        if o<=hard:return ('HARD_STOP',t)
        if o>=target:return ('TAKE_PROFIT',t)
        if l<=hard and h>=target:return ('AMBIGUOUS',t)
        if l<=hard:return ('HARD_STOP',t)
        if h>=target:return ('TAKE_PROFIT',t)
    return ('UNRESOLVED',None)


def analyze(packet,bars,observations,signals,context,execution):
    hours=packet['rows'];cache={};result=dict(version='btc-bear-target-breakout-crash-v3',source_signature=packet['source_signature'],protocol=json.loads((OUT/'protocol.json').read_text()),variants={},breakout_branches={},data=dict(hour_candles=len(hours),five_minute_candles=len(bars),ready_context_bars=sum(f.ready for f in observations)),policies={},audit={})
    methods=['forming_hour_drop_with_5m_peak','forming_hour_extreme_with_5m_peak']
    gates=['immediate','avoid_recent_crash','avoid_unrecovered_crash','wait_micro_reclaim','wait_range_low_reclaim','wait_volume_breakout']
    entry_catalog={};bar_index={b[0]:i for i,b in enumerate(bars)}
    for method in methods:
      for threshold in (40,45,50):
       for rsi_mode in ('none','signal'):
        for gate in gates:
            entries,reasons=candidates(signals,bars,observations,context,threshold,rsi_mode,method,gate,bar_index)
            entry_catalog.update({e['entry_time']:e for e in entries})
            key=f'{method}_di{threshold}_rsi_{rsi_mode}_{gate}';item=dict(candidate_entries=len(entries),filter_counts=reasons,gate=gate,method=method,threshold=threshold,rsi_mode=rsi_mode,replays={})
            policies=dict(new_exit=Policy(),literal_price_stop=Policy(risk='price_0_5pct'))
            if gate=='immediate':policies.update(old_exit=Policy(bearish_exit='trail'),entry_regime_exit=Policy(regime_mode='entry'),price_target_basis=Policy(bearish_target_basis='price_1pct'))
            for name,policy in policies.items():
                result['policies'][name]=asdict(policy)
                item['replays'][name]={order:run_portfolio(entries,hours,execution,context,policy,cache,order) for order in ('low_first','high_first')}
            result['variants'][key]=item
            print(key,json.dumps({k:item['replays']['new_exit']['low_first'][k] for k in ('closed','win_pct','mean_net_pct','profit_factor')}),flush=True)
    for name in ('breakout_up','breakout_retest'):
        entries=breakout_candidates(bars,observations,context,hours,name);entry_catalog.update({e['entry_time']:e for e in entries})
        policy=Policy();result['breakout_branches'][name]=dict(candidate_entries=len(entries),replays={order:run_portfolio(entries,hours,execution,context,policy,cache,order) for order in ('low_first','high_first')})
        # A real old execution-data gap must not be silently treated as a closed
        # trade. Separate flat-start periods still permit assessment of later
        # windows, explicitly without claiming one continuous account curve.
        reset={}
        for label,lo,hi in [('2017_2023',0,1704067200000),('2024',1704067200000,1735689600000),('2025_2026',1735689600000,math.inf)]:
            subset=[e for e in entries if lo<=e['entry_time']<hi]
            reset[label]={order:run_portfolio(subset,hours,execution,context,policy,cache,order) for order in ('low_first','high_first')}
        result['breakout_branches'][name]['separate_flat_start_periods']=reset
        print('bullish',name,result['breakout_branches'][name]['candidate_entries'],flush=True)
    # Audit the same frozen-price path using direct independent barrier searches.
    audit_policy=Policy(regime_mode='entry');audited=0;ambiguous=0;errors=[];examples=[]
    baseline=[s for s in signals if s['method']=='forming_hour_drop_with_5m_peak' and s['peak_di_minus']>40 and s['entry_regime']=='BEARISH']
    seen=set()
    for s in baseline:
        if s['entry_time'] in seen:continue
        seen.add(s['entry_time']);override={k:s[k] for k in ('signal_time','entry_time','entry_open','entry_regime')}
        pair=base.paired_trade(hours,min(s['hour_index'],len(hours)-2),execution,context,audit_policy,override)
        tr=pair[0]
        if tr['status']!='CLOSED':continue
        reference,bar_time=reference_barrier(s,audit_policy,execution,tr['execution_tf'])
        if reference=='AMBIGUOUS':ambiguous+=1;continue
        audited+=1
        if reference!=tr['reason'] or bar_time!=tr['exit_bar_time']:errors.append(dict(entry_time=s['entry_time'],reference=reference,model=tr))
        if len(examples)<12:examples.append(dict(entry_time=s['entry_time'],oracle=reference,exit_bar_time=bar_time,net_pct=tr['net_pct'],execution_tf=tr['execution_tf']))
    result['audit']=dict(independent_bearish_barrier_checks=audited,intrabar_ambiguous_excluded=ambiguous,mismatches=errors,examples=examples)
    if errors:raise AssertionError('Independent barrier audit failed')
    # Label only observed events. These classifications never inspect future bars.
    result['market_event_counts']={key:sum(f[key] for f in observations) for key in ('breakout_up','breakdown','crash','micro_reclaim','range_low_reclaim','breakout_retest')}
    # Diagnostic labels only: how often a stopped trade later visited the target.
    # They are never supplied to entry filters or used to relabel losing trades.
    result['stop_then_later_target']={}
    price_index={b[0]:k for k,b in enumerate(bars)}
    for threshold in (40,45,50):
        variant=result['variants'][f'forming_hour_drop_with_5m_peak_di{threshold}_rsi_none_immediate']['replays']['new_exit']['low_first']
        stops=[]
        for t in variant['accepted_entry_times']:
            tr=cache[(t,Policy())][0]
            if tr.get('reason')!='HARD_STOP':continue
            k=price_index.get(t)
            if k is None or k+72>len(bars):continue
            window=bars[k:k+72]
            if any(b[0]!=t+j*features.STEP for j,b in enumerate(window)):continue
            later=any(b[0]>tr['exit_bar_time'] and b[3]>=tr['activation_price'] for b in window)
            stops.append(later)
        result['stop_then_later_target'][str(threshold)]=dict(stopped_trades_with_complete_6h_window=len(stops),target_seen_in_a_later_5m_bar=sum(stops),pct=100*sum(stops)/len(stops) if stops else None)
    result['entry_cases']=[dict(entry_time=t,policy=asdict(p),traces=traces) for (t,p),traces in cache.items()]
    result['entry_catalog']=sorted(entry_catalog.values(),key=lambda e:e['entry_time'])
    return result

if __name__=='__main__':
    packet=json.loads(gzip.decompress(base.SOURCE.read_bytes()));bars=json.loads(gzip.decompress((V2/'five_minute_source.json.gz').read_bytes()));volumes=freeze_volumes(bars)
    print('frozen volumes',len(volumes),'missing',sum(v is None for v in volumes),flush=True)
    observations=features.observe(bars,volumes);print('market events computed',flush=True)
    signals,context,quality=intra.make_signals(packet,bars);print('causal previews verified',quality['terminal_preview_parity'],flush=True)
    blocks=OUT/'execution_blocks.json.gz';cached=json.loads(gzip.decompress((blocks if blocks.exists() else V2/'intrabar_execution_blocks.json.gz').read_bytes()));execution=base.Execution(packet['rows'][-1]['close_time'],cached)
    try:
        result=analyze(packet,bars,observations,signals,context,execution);result['data_quality']=quality
        result['code_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),OUT/'features.py',V2/'replay.py')}
        (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        events=[dict(time=bars[k][0],**asdict(f)) for k,f in enumerate(observations) if f.breakout_up or f.breakdown or f.crash or f.breakout_retest or f.range_low_reclaim]
        (OUT/'market_events.json.gz').write_bytes(gzip.compress(json.dumps(events,separators=(',',':'),allow_nan=False).encode(),mtime=0))
    finally:
        blocks.write_bytes(gzip.compress(json.dumps(execution.cache,separators=(',',':'),allow_nan=False).encode(),mtime=0));execution.close()
