"""User-specified DI−/spread peaks and simultaneous DI+ trough, spot only."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))

from bisect import bisect_right
from collections import Counter
from dataclasses import asdict, replace
import argparse
import gc
import gzip
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time

from Section_8_Decision_Engine import strategy_analyzer as analyzer, strategy_memory
from Section_8_Decision_Engine import strategy_exits
from Section_8_Decision_Engine.pivot_candle_source import unpack
from Section_1_Global_Core import regime_inputs
from Section_4_Features.execution.components import catalog
from Section_5_Market_Regime.engines import structure,trend,regime
from Section_12_Research.reports.BTC_1h_di_spread_trailing_v2 import replay as execution_base
from Section_12_Research.reports.BTC_1h_bear_target_breakouts_v3.study import Policy

OUT=Path(__file__).parent
STEP=900000
VARIANTS=('peak_thresholds_with_plus','current_thresholds_with_plus','peak_thresholds_without_plus','current_thresholds_without_plus',
          'peak_thresholds_plus_non_decreasing','current_thresholds_plus_non_decreasing')


def predicate(field,op,*,value=None,lag=0,other_lag=None):
    p=dict(field=field,op=op,lag=lag)
    if other_lag is None:p['value']=value
    else:p.update(other_field=field,other_lag=other_lag)
    return p


def configuration(variant='peak_thresholds_with_plus'):
    threshold_lag=0 if variant.startswith('current') else 1
    conditions=[predicate('context.15m.TREND.direction','eq',value='BEARISH'),
                predicate('di.di_minus','gt',value=50,lag=threshold_lag),
                predicate('di.abs_spread','gt',value=50,lag=threshold_lag)]
    for field in ('di.di_minus','di.abs_spread'):
        conditions.extend([predicate(field,'lt',lag=2,other_lag=1),predicate(field,'lt',lag=0,other_lag=1)])
    if variant.endswith('with_plus'):
        conditions.extend([predicate('di.di_plus','gt',lag=2,other_lag=1),predicate('di.di_plus','gt',lag=0,other_lag=1)])
    elif variant.endswith('plus_non_decreasing'):
        conditions.append(predicate('di.di_plus','gte',lag=0,other_lag=1))
    conditions.append(predicate('context.15m.REGIME.direction','in',value=['BEARISH','BULLISH']))
    return dict(version=analyzer.VERSION,id='DI50 bearish '+variant,
                description='User hypothesis: bearish 15m Trend; strict DI− and absolute-spread peaks; DI+ trough. No RSI filter. Entry regime must support the previously agreed exit policy.',
                execution=dict(fee_bps_per_side=4,slippage_bps_per_side=2,initial_capital=100,intrabar_path='low_first'),
                branches=[dict(id='di50_buy',side='BUY',when=dict(all=conditions)),
                          dict(id='bearish_target_1pct',side='SELL',action='TAKE_PROFIT',target_profit_pct=1,
                               when=predicate('context.15m.REGIME.direction','eq',value='BEARISH')),
                          dict(id='bullish_trail',side='SELL',action='TRAILING_SELL',trail=dict(activation_profit_pct=1,distance_pct=.5),
                               when=dict(all=[predicate('context.15m.REGIME.direction','eq',value='BULLISH'),predicate('di.di_plus','gt',value=50)]))])


def direction(row,engine):
    p=row.get('context',{}).get(engine,{})
    return (p.get('classification') or {}).get('direction','UNKNOWN') if p.get('data_quality') in ('VALID','PARTIAL') else 'UNKNOWN'


def valid(row):
    f=row['features']
    prices=all(execution_base.finite(row.get(k)) and row[k]>0 for k in ('open','high','low','close'))
    return prices and row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high'] and row['close_time']==row['open_time']+STEP-1 and row.get('feature_valid',True) and not f.get('measurement_gap') and all(execution_base.finite(f.get(k)) and 0<=f[k]<=100.000001 for k in ('di_plus','di_minus'))


def thin(source):
    source=unpack(source);rows=[]
    for r in source['candles']:
        contexts={}
        for engine in ('TREND','REGIME'):
            p=r.get('context',{}).get(engine) or source.get('engine_history',{}).get('15m:'+engine,{}).get('results',{}).get(str(r['open_time']))
            contexts[engine]=p or dict(data_quality='UNAVAILABLE',classification=dict(direction='UNKNOWN'))
        rows.append(dict(**{k:r[k] for k in ('open_time','close_time','open','high','low','close')},
                         feature_valid=r.get('feature_valid',True),features={k:r['features'].get(k) for k in ('di_plus','di_minus','measurement_gap','prev_di_plus','prev_di_minus','di_spread')},context=contexts))
    meta={k:source.get(k) for k in ('version','symbol','timeframe','source_id','observed_as_of','source_metadata','memory')}
    return rows,meta


def setups(rows):
    groups={v:[] for v in VARIANTS};funnel=Counter();threshold_counts={v:Counter() for v in VARIANTS}
    parity=Counter()
    for i,r in enumerate(rows):
        if not valid(r):continue
        funnel['valid_feature_candles']+=1
        td=direction(r,'TREND');funnel['trend_'+td]+=1
        if i and rows[i-1]['close_time']+1==r['open_time'] and valid(rows[i-1]):
            for field in ('di_plus','di_minus'):
                if execution_base.finite(r['features'].get('prev_'+field)):
                    parity[field+'_checked']+=1
                    parity[field+'_mismatched']+=not math.isclose(r['features']['prev_'+field],rows[i-1]['features'][field],abs_tol=1e-8)
        if i<2:continue
        a,b,c=rows[i-2:i+1]
        if not all(valid(x) for x in (a,b,c)) or a['close_time']+1!=b['open_time'] or b['close_time']+1!=c['open_time']:continue
        funnel['valid_three_candle_windows']+=1
        minus=[x['features']['di_minus'] for x in (a,b,c)];plus=[x['features']['di_plus'] for x in (a,b,c)]
        spread=[abs(m-p) for m,p in zip(minus,plus)]
        if not (minus[2]<minus[1] and minus[0]<minus[1] and spread[2]<spread[1] and spread[0]<spread[1]):continue
        funnel['minus_and_spread_strict_peaks']+=1
        if not (minus[1]>50 and spread[1]>50):continue
        funnel['peaks_above_50']+=1
        trough=plus[0]>plus[1] and plus[2]>plus[1]
        if trough:funnel['peaks_above_50_plus_trough']+=1
        if plus[2]>=plus[1]:funnel['peaks_above_50_plus_non_decreasing']+=1
        for variant in VARIANTS:
            if variant.startswith('current') and not (minus[2]>50 and spread[2]>50):continue
            if variant.endswith('with_plus') and not trough:continue
            if variant.endswith('plus_non_decreasing') and plus[2]<plus[1]:continue
            counts=threshold_counts[variant];counts['indicator_setups']+=1
            if td not in ('BEARISH','BULLISH','NEUTRAL'):counts['missing_trend']+=1;continue
            if td!='BEARISH':counts['non_bearish_trend']+=1;continue
            counts['bearish_trend_setups']+=1
            rd=direction(r,'REGIME')
            if rd not in ('BEARISH','BULLISH'):counts['neutral_or_unknown_exit_regime']+=1;continue
            if i+1>=len(rows) or r['close_time']+1!=rows[i+1]['open_time']:counts['missing_next_open']+=1;continue
            counts['eligible_entries']+=1;groups[variant].append(i)
    return groups,dict(funnel),{v:dict(c) for v,c in threshold_counts.items()},dict(parity)


class Context:
    def __init__(self,rows):self.rows=rows;self.known=[r['close_time']+1 for r in rows]
    def at(self,stamp):
        i=bisect_right(self.known,stamp)-1
        if i<0 or stamp-self.known[i]>=STEP:return 'UNKNOWN',None
        r=self.rows[i]
        return direction(r,'REGIME'),r['features'].get('di_plus') if valid(r) else None


class Execution(execution_base.Execution):
    def __init__(self,symbol,rows,until):
        super().__init__(until);self.symbol=symbol;self.rows=rows;self.positions={r['open_time']:i for i,r in enumerate(rows)};self.quality=Counter()
    def block(self,stamp,tf):
        if tf=='15m':return []
        step=60000 if tf=='1m' else 300000;start=stamp//(240*step)*(240*step);key=f'{tf}:{start}'
        if key not in self.cache:
            if self.conn is None:self.conn=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)
            raw=[list(r) for r in self.conn.execute('SELECT open_time,close_time,open,high,low,close FROM klines WHERE symbol=? AND interval=? AND open_time>=? AND open_time<? AND close_time<=? ORDER BY open_time',(self.symbol,tf,start,start+240*step,self.until)).fetchall()]
            groups={}
            for r in raw:groups.setdefault(r[0]//STEP*STEP,[]).append(r)
            accepted=[]
            for opened,parts in groups.items():
                if len(parts)!=STEP//step or any(p[0]!=opened+j*step or p[1]!=p[0]+step-1 for j,p in enumerate(parts)):
                    self.quality[tf+'_incomplete_15m_groups']+=1;continue
                reference=self.rows[self.positions[opened]] if opened in self.positions else None
                aggregated=[parts[0][2],max(p[3] for p in parts),min(p[4] for p in parts),parts[-1][5]]
                if reference and any(not math.isclose(x,reference[k],rel_tol=1e-9,abs_tol=1e-12) for x,k in zip(aggregated,('open','high','low','close'))):
                    self.quality[tf+'_mismatched_15m_groups']+=1;continue
                accepted.extend(parts)
            self.cache[key]=accepted
        return self.cache[key]
    def bars(self,start,tf):
        if tf!='15m':yield from super().bars(start,tf);return
        at=self.positions.get(start)
        if at is None:return
        expected=start
        for i in range(at,len(self.rows)):
            r=self.rows[i]
            if r['open_time']!=expected or r['close_time']>self.until:return
            yield [r[k] for k in ('open_time','close_time','open','high','low','close')]
            expected=r['close_time']+1


def replay_one(rows,i,execution,context,policy,order,tf):
    """Use the current workspace's exit manager at recorded lower-timeframe prices."""
    opened=rows[i+1]['open_time'];raw_entry=rows[i+1]['open'];entry,hard,trigger=execution_base.levels(raw_entry,policy)
    entry_regime=direction(rows[i],'REGIME');position=dict(entry=entry,stop_price=hard);last=None;count=unknown=0;arm_regime=None
    for values in execution.bars(opened,tf):
        t,closed,o,h,l,c=values;count+=1;last=values
        if not all(execution_base.finite(p) and p>0 for p in (o,h,l,c)) or not l<=min(o,c)<=max(o,c)<=h:break
        current,plus=context.at(t)
        if policy.regime_mode=='entry':current=entry_regime
        if current not in ('BEARISH','BULLISH'):unknown+=1
        eligible=[]
        if current=='BEARISH' and policy.bearish_exit=='fixed_target':
            eligible=[dict(id='bear_target',action='TAKE_PROFIT',target_profit_pct=1)]
        elif current=='BEARISH' or current=='BULLISH' and execution_base.finite(plus) and plus>50:
            eligible=[dict(id='regime_trail',action='TRAILING_SELL',trail=dict(activation_profit_pct=1,distance_pct=.5))]
        was_armed=position.get('trail_branch')
        row=dict(open_time=t,close_time=closed,open=o,high=h,low=l,close=c)
        result=strategy_exits.walk(position,row,eligible,policy.fee,policy.slip,order)
        if position.get('trail_branch') and not was_armed:arm_regime=current
        if result:
            ref=result['raw_price']
            return dict(status='CLOSED',reason=result['reason'],signal_time=rows[i]['open_time'],signal_known_time=rows[i]['close_time']+1,
                        entry_time=opened,entry_open=raw_entry,entry_fill=entry,entry_regime=entry_regime,hard_stop=hard,activation_price=trigger,
                        exit_bar_time=t,exit_time_upper=result['time'],exit_reference=ref,net_pct=execution_base.net(ref,entry,policy),
                        price_pct=(ref/entry-1)*100,armed=bool(position.get('trail_branch')),armed_time=position.get('trail_armed_at'),arm_regime=arm_regime,
                        highest=position['peak'],bars=count,execution_tf=tf,order=order,ambiguous_stop_bar=(l<=hard and h>=trigger) or bool(position.get('trail_branch') and h>=trigger and l<=h*(1-policy.trail)),
                        unknown_context_bars=unknown,holding_minutes_upper=(result['time']-opened)/60000)
    complete=last is not None and last[1]>=execution.until
    return dict(status='OPEN_AT_BOUNDARY' if complete else 'EXECUTION_GAP',signal_time=rows[i]['open_time'],entry_time=opened,entry_regime=entry_regime,
                armed=bool(position.get('trail_branch')),execution_tf=tf,order=order,bars=count,last_bar_time=last[0] if last else None,
                last_known_mtm_pct=execution_base.net(last[5],entry,policy) if last else None,unknown_context_bars=unknown)


def paired(rows,i,execution,context,policy):
    reasons=[]
    for tf in ('1m','5m','15m'):
        first=next(execution.bars(rows[i+1]['open_time'],tf),None)
        if first is None or not math.isclose(first[2],rows[i+1]['open'],rel_tol=1e-9,abs_tol=1e-12):
            reasons.append(tf+': missing or mismatched entry open');continue
        result=[replay_one(rows,i,execution,context,policy,order,tf) for order in ('low_first','high_first')]
        if any(t['status'] in ('EXECUTION_GAP','ENTRY_PRICE_MISMATCH') for t in result) and tf!='15m':
            reasons.append(tf+': execution gap');continue
        for t in result:t['lower_timeframe_fallbacks']=list(reasons)
        return result
    raise AssertionError('15m source entry should be available')


def analyze(rows,meta,*,include_trailing_sensitivity=False,verify_rules=False):
    groups,funnel,counts,parity=setups(rows);context=Context(rows)
    policies={'agreed_regime_exits':Policy()}
    if include_trailing_sensitivity:policies['bearish_trail_sensitivity']=replace(Policy(),bearish_exit='trail')
    execution=Execution(meta['symbol'],rows,rows[-1]['close_time']);cache={};variants={}
    try:
        for variant,indices in groups.items():
            replays={}
            for policy_name,policy in policies.items():
                paths={}
                for order in ('low_first','high_first'):
                    accepted=[];blocked=-1;overlap=0
                    for i in indices:
                        if rows[i+1]['open_time']<blocked:overlap+=1;continue
                        cache_key=(i,policy_name)
                        if cache_key not in cache:cache[cache_key]=paired(rows,i,execution,context,policy)
                        trace=next(t for t in cache[cache_key] if t['order']==order)
                        accepted.append(trace);blocked=trace['exit_time_upper'] if trace['status']=='CLOSED' else math.inf
                    summary=execution_base.portfolio(accepted);summary['overlap_skipped']=overlap
                    summary['by_entry_regime']={d:execution_base.summarize([t for t in accepted if t['entry_regime']==d]) for d in ('BEARISH','BULLISH')}
                    paths[order]=dict(summary=summary,trades=accepted)
                replays[policy_name]=paths
            variants[variant]=dict(funnel=counts[variant],replays=replays)
        config_parity=None
        if verify_rules:
            source=dict(version='memory-candle-source-v1',symbol=meta['symbol'],timeframe='15m',source_id=meta['source_id'],observed_as_of=meta['observed_as_of'],candles=rows,engine_history={})
            memory=analyzer.Memory(source);checks=0
            sample=set(range(2,len(rows),997))|{i for ids in groups.values() for i in ids}
            for v,ids in groups.items():
                expected=set(ids);expression=configuration(v)['branches'][0]['when']
                for i in sample:
                    if i+1>=len(rows) or rows[i]['close_time']+1!=rows[i+1]['open_time']:continue
                    actual=memory.evaluate(expression,i,set()) is True
                    if actual!=(i in expected):raise AssertionError(f'Workspace predicate mismatch: {meta["symbol"]} {v} {i}')
                    checks+=1
            config_parity=dict(checks=checks,mismatches=0)
        return dict(source=meta,candles=len(rows),first=rows[0]['open_time'],last=rows[-1]['close_time']+1,
                    indicator_funnel=funnel,stored_previous_di_parity=parity,variants=variants,workspace_condition_parity=config_parity,
                    policies={name:asdict(p) for name,p in policies.items()},lower_timeframe_quality=dict(execution.quality),case_traces=[dict(signal_index=i,policy=name,traces=traces) for (i,name),traces in cache.items()]),execution.cache
    finally:execution.close()


def frozen(symbol):
    path=OUT.parent/'pivot_discovery'/f'{symbol}_15m_source.json.gz'
    with gzip.open(path,'rt') as f:source=json.load(f)
    feature_catalog=catalog();fields=source['exported_feature_columns']+['structure_events']
    fields=tuple(sorted(f for f in fields if f not in feature_catalog.export_inverse or feature_catalog.export_inverse[f] in feature_catalog.final))
    conn=regime_inputs.open_sources()
    try:
        if regime_inputs.source_metadata(conn,symbol,'15m','initial',fields)!=source['source_metadata']:raise ValueError('Frozen snapshot no longer matches current feature generation/config')
    finally:conn.close()
    for name,module in [('STRUCTURE',structure),('TREND',trend),('REGIME',regime)]:
        if source['engines'][name]['source_sha256']!=hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest():raise ValueError('Frozen classifier definitions changed')
    rows,meta=thin(source);meta['basis']='FROZEN_STORED_MEASUREMENTS_WITH_COMPLETE_OFFLINE_CONTEXT';meta['file']=str(path);meta['file_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    return rows,meta


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value,separators=(',',':'),allow_nan=False).encode()
    temp=path.with_name(path.name+'.partial');temp.write_bytes(gzip.compress(raw,compresslevel=1,mtime=0) if path.suffix=='.gz' else raw);temp.replace(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--memory',action='store_true');parser.add_argument('--symbols',nargs='+');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    for v in VARIANTS:
        config=configuration(v);analyzer.validate_config(config);save(OUT/'configs'/(v+'.json'),config)
    protocol=dict(version='di50-three-candle-study-v1',timeframe='15m',thresholds='Strict >50; peak thresholds and still-above-50 confirmation thresholds are separate predefined variants',
                  turns='DI−[2] < DI−[1] > DI−[0]; abs spread[2] < spread[1] > spread[0]; DI+[2] > DI+[1] < DI+[0]',
                  interpretation_sensitivity='The literal DI+ did not decrease version only requires DI+[0] >= DI+[1], without a prior DI+ decline. The strict three-candle trough remains the primary rule.',
                  trend='Same-timeframe confirmed Trend.direction BEARISH at the signal close; missing Trend excluded and counted',
                  entry='Next contiguous 15m open; no RSI condition; one position per coin',exit='0.5% net hard-stop budget from entry. Current last-closed bearish Regime: fixed +1% net target. Bullish: profit >=1% AND DI+ >50 arms a permanent 0.5% highest-since-entry trail. Neutral/unknown entry Regime excluded and counted; while holding, unknown Regime cannot arm a new exit.',
                  execution='Stored continuous 1m, otherwise 5m, otherwise labeled 15m source. Both low-first/high-first OHLC paths; no fixed holding timeout; actual adverse opens retained. Unresolved positions occupy capital.',
                  costs=dict(fee_bps_per_side=4,slippage_bps_per_side=2),reference='No pivot labels select entries. Frozen complete reconstructed context and partial current memory are reported separately; no new classifiers run.')
    save(OUT/'protocol.json',protocol)
    symbols=args.symbols or (sorted({p['symbol'] for p in strategy_memory.universe()['pairs'] if p['timeframe']=='15m'}) if args.memory else ['BTCUSDT','SUIUSDT'])
    index={};cutoff=int(time.time()*1000)
    for symbol in symbols:
        try:
            if args.memory:
                source=strategy_memory.load(symbol,'15m',until=cutoff,fields=['feature.prev_di_plus','feature.prev_di_minus','feature.di_spread','context.15m.TREND.direction','context.15m.REGIME.direction'])
                rows,meta=thin(source);meta['basis']='CURRENT_STORED_MEMORY_PARTIAL_CONTEXT';del source
            else:rows,meta=frozen(symbol)
            gc.collect();result,blocks=analyze(rows,meta,include_trailing_sensitivity=not args.memory,verify_rules=symbol in ('BTCUSDT','SUIUSDT'))
            basis='memory' if args.memory else 'frozen';stem=basis+'_'+symbol
            save(OUT/(stem+'_results.json.gz'),result);save(OUT/(stem+'_execution.json.gz'),dict(symbol=symbol,until=rows[-1]['close_time'],blocks=blocks))
            headline={v:dict(funnel=r['funnel'],**r['replays']['agreed_regime_exits']['low_first']['summary']) for v,r in result['variants'].items()}
            index[symbol]=dict(status='complete',source=meta,candles=len(rows),indicator_funnel=result['indicator_funnel'],variants=headline)
            print(json.dumps(dict(symbol=symbol,basis=basis,candles=len(rows),trend_known=sum(result['indicator_funnel'].get('trend_'+d,0) for d in ('BEARISH','BULLISH','NEUTRAL')),setups={v:c['funnel'].get('eligible_entries',0) for v,c in headline.items()})),flush=True)
            del rows,result,blocks;gc.collect()
        except Exception as error:
            index[symbol]=dict(status='failed',error=str(error));print(json.dumps(dict(symbol=symbol,error=str(error))),flush=True)
        save(OUT/('memory_summary.json' if args.memory else 'frozen_summary.json'),index)


if __name__=='__main__':main()
