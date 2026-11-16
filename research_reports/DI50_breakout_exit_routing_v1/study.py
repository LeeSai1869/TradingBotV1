"""Same DI50 entries: gross quick exits versus causally selected breakout runners."""
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, asdict
import gc
import gzip
import hashlib
import json
import math
from pathlib import Path

from Section_8_Decision_Engine import strategy_exits as exits, strategy_memory
from Section_8_Decision_Engine.pivot_candle_source import unpack
from research_reports.DI50_15m_three_candle_reversal import study as prior

OUT=Path(__file__).parent
PREVIOUS=prior.OUT
FEE=.0004
SLIP=.0002
STEP5=300000


def net_equivalent(gross_pct):
    """Gross = reference-price appreciation from raw entry open, before all costs."""
    return ((1+gross_pct/100)*(1-SLIP)*(1-FEE)/((1+SLIP)*(1+FEE))-1)*100


def net_return(reference,entry_fill):
    value=(reference*(1-SLIP)*(1-FEE)/(entry_fill*(1+FEE))-1)*100
    return 0.0 if abs(value)<1e-10 else value


@dataclass(frozen=True)
class Policy:
    name:str
    target:float=1
    basis:str='gross'
    gate:str='none'
    protect:bool=False


POLICIES=[Policy('old_regime_reference'),Policy('fixed_1_net',basis='net'),Policy('fixed_1_gross'),Policy('fixed_0_5_gross',target=.5),Policy('trail_all',gate='all')]
for gate in ('entry_expansion','micro_reclaim','volume_breakout'):
    for target in (.5,1):POLICIES.append(Policy(f'hybrid_{str(target).replace(".","_")}_{gate}',target=target,gate=gate))
POLICIES.append(Policy('hybrid_0_5_volume_protected',target=.5,gate='volume_breakout',protect=True))


def read(path):
    with gzip.open(path,'rt') as f:return json.load(f)


def position_in_candle(row):
    return (row['close']-row['low'])/(row['high']-row['low']) if row['high']>row['low'] else .5


def entry_features(full_rows,index):
    row=full_rows[index];f=row['features'];previous=full_rows[index-1]
    span=row['high']-row['low'];position=position_in_candle(row)
    number=lambda key:f.get(key) if prior.execution_base.finite(f.get(key)) else None
    expansion=(row['close']>row['open'] and row['close']>previous['high'] and position>=.7
               and number('relative_volume') is not None and f['relative_volume']>=1.5
               and number('candle_range_atr') is not None and f['candle_range_atr']>=1.2)
    return dict(relative_volume=number('relative_volume'),natr_pct=number('natr_pct'),candle_range_atr=number('candle_range_atr'),
                close_position=position,lower_wick_fraction=(min(row['open'],row['close'])-row['low'])/span if span>0 else None,
                plus_rise=f['di_plus']-previous['features']['di_plus'],minus_drop=previous['features']['di_minus']-f['di_minus'],
                close_to_ema50_pct=100*(row['close']/f['ema50']-1) if number('ema50') and f['ema50']>0 else None,
                entry_expansion=expansion,measurement_config_id=f.get('measurement_config_id'))


class Observations:
    """Only stored 5m measurements and ranges made of already closed candles."""
    def __init__(self,rows,entry,config_id):
        self.values=[];self.known=[];history=[];last=None;last_crash=None
        for row in rows:
            if last is not None and row['open_time']!=last:history=[];last_crash=None
            f=row['features'];ready=len(history)>=12 and row.get('feature_valid') and not f.get('measurement_gap') and f.get('measurement_config_id')==config_id
            current=dict(known=row['close_time']+1,ready=bool(ready),close=row['close'],rvol=f.get('relative_volume'),range_atr=f.get('candle_range_atr'),
                         di_plus=f.get('di_plus'),di_minus=f.get('di_minus'),micro_reclaim=False,volume_breakout=False,crash_unrecovered=False)
            if ready:
                high3=max(r['high'] for r in history[-3:]);high12=max(r['high'] for r in history[-12:]);low12=min(r['low'] for r in history[-12:])
                p=position_in_candle(row);rvol=f.get('relative_volume');scale=f.get('candle_range_atr')
                micro=row['close']>high3 and row['close']>row['open'] and p>=.6
                volume=micro and row['close']>high12 and p>=.7 and prior.execution_base.finite(rvol) and rvol>=1.5 and prior.execution_base.finite(scale) and scale>=1.2
                ret=100*(row['close']/history[-1]['close']-1);ret3=100*(row['close']/history[-3]['close']-1)
                crash=row['close']<low12 and p<=.3 and prior.execution_base.finite(rvol) and rvol>=1.5 and prior.execution_base.finite(scale) and scale>=1.5 and (ret<=-.5 or ret3<=-1)
                if crash:last_crash=(row['close_time']+1,row['high'])
                if last_crash and row['close']>last_crash[1]:last_crash=None
                current.update(micro_reclaim=micro,volume_breakout=volume,micro_level=high3,volume_level=high12,close_position=p,
                               crash_unrecovered=bool(last_crash and row['close_time']+1-last_crash[0]<=15*60000))
            self.values.append(current);self.known.append(current['known'])
            history.append(row);history=history[-20:];last=row['close_time']+1
        self.entry=entry

    def at(self,t):
        i=bisect_right(self.known,t)-1
        if i<0 or t-self.known[i]>=STEP5:return dict(known=None,ready=False)
        return self.values[i]

    def gate(self,name,t,price,entry_info):
        if name=='all':return True,dict(known=self.entry,gate='all')
        if name=='entry_expansion':return entry_info['entry_expansion'],dict(known=self.entry,gate=name)
        point=self.at(t)
        if name=='none' or not point.get('ready'):return False,point
        level='micro_level' if name=='micro_reclaim' else 'volume_level'
        return bool(point.get(name) and price>=point.get(level,math.inf)),point


def protect_walk(position,row,eligible,order):
    """Raise the stop to net breakeven at an observed +0.5% gross crossing."""
    threshold=position['entry_open']*1.005
    if position.get('protected'):return exits.walk(position,row,eligible,FEE,SLIP,order)
    points=[row['open'],row['low'],row['high'],row['close']] if order=='low_first' else [row['open'],row['high'],row['low'],row['close']]
    def promote():
        position['stop_price']=max(position['stop_price'],exits.trigger_price(position,0,FEE,SLIP))
        position['protected']=True
    if points[0]>=threshold:promote();return exits.walk(position,row,eligible,FEE,SLIP,order)
    for j,(a,b) in enumerate(zip(points,points[1:])):
        endpoints=[threshold,b] if not position.get('protected') and a<threshold<=b else [b]
        for k,end in enumerate(endpoints):
            piece=dict(row,open=a,high=max(a,end),low=min(a,end),close=end)
            result=exits.walk(position,piece,eligible,FEE,SLIP,'low_first' if end>=a else 'high_first')
            if result:
                if j or k or result['precision']!='OPEN':result.update(time=row['close_time']+1,precision='WITHIN_CANDLE_UNKNOWN')
                return result
            if not position.get('protected') and end>=threshold:promote()
            a=end
    return None


def simulate(rows,index,execution,obs,entry_info,policy,order,tf):
    if policy.name=='old_regime_reference':return prior.replay_one(rows,index,execution,prior.Context(rows),prior.Policy(),order,tf)
    start=rows[index+1]['open_time'];raw_entry=rows[index+1]['open'];fill=raw_entry*(1+SLIP)
    position=dict(entry=fill,entry_open=raw_entry,stop_price=exits.trigger_price(dict(entry=fill),-.5,FEE,SLIP))
    selected=False;proof=None;last=None;count=0
    for values in execution.bars(start,tf):
        t,end,o,h,l,c=values;last=values;count+=1
        if not selected and policy.gate!='none':
            hit,evidence=obs.gate(policy.gate,t,o,entry_info)
            if hit:selected=True;proof=dict(evidence,selected_at=t);assert evidence['known']<=t
        target=policy.target if policy.basis=='net' else net_equivalent(policy.target)
        eligible=[dict(id='breakout_trail',action='TRAILING_SELL',trail=dict(activation_profit_pct=net_equivalent(1),distance_pct=.5))] if selected else [dict(id='quick_profit',action='TAKE_PROFIT',target_profit_pct=target)]
        row=dict(open_time=t,close_time=end,open=o,high=h,low=l,close=c)
        result=protect_walk(position,row,eligible,order) if selected and policy.protect else exits.walk(position,row,eligible,FEE,SLIP,order)
        if result:
            ref=result['raw_price'];net=net_return(ref,fill);reason=result['reason']
            if reason=='HARD_STOP' and position.get('protected'):reason='BREAKEVEN_STOP' if net==0 else 'PROTECTED_STOP_GAP'
            return dict(status='CLOSED',reason=reason,signal_time=rows[index]['open_time'],signal_known_time=rows[index]['close_time']+1,
                        entry_time=start,entry_open=raw_entry,entry_fill=fill,entry_regime=prior.direction(rows[index],'REGIME'),
                        exit_bar_time=t,exit_time_upper=result['time'],exit_reference=ref,net_pct=net,gross_reference_pct=100*(ref/raw_entry-1),
                        execution_tf=tf,order=order,bars=count,highest=position['peak'],max_gross_before_exit_pct=100*(position['peak']/raw_entry-1),
                        selected_breakout=selected,breakout_evidence=proof,protected=position.get('protected',False),armed=bool(position.get('trail_branch')),
                        holding_minutes_upper=(result['time']-start)/60000)
    return dict(status='OPEN_AT_BOUNDARY' if last and last[1]>=execution.until else 'EXECUTION_GAP',entry_time=start,entry_regime=prior.direction(rows[index],'REGIME'),execution_tf=tf,order=order,selected_breakout=selected,breakout_evidence=proof)


def summaries(trades):
    p=prior.execution_base.portfolio(trades);closed=[t for t in trades if t['status']=='CLOSED'];accepted=[];blocked=-1
    for t in trades:
        if t['entry_time']<blocked:continue
        accepted.append(t);blocked=t['exit_time_upper'] if t['status']=='CLOSED' else math.inf
    p.update(breakeven=sum(t.get('net_pct')==0 for t in accepted if t['status']=='CLOSED'),selected_breakouts=sum(t.get('selected_breakout',False) for t in accepted),
             isolated_opportunities=len(trades),isolated_closed=len(closed),accepted_entry_times=[t['entry_time'] for t in accepted])
    return p


def post_stop(execution,trade,horizon=240):
    start=trade['exit_time_upper'];until=min(execution.until+1,start+horizon*60000);result=None
    for tf in dict.fromkeys((trade['execution_tf'],'5m','15m')):
        bars=[]
        # At coarser fallback, start from the first fully subsequent candle.
        step={'1m':60000,'5m':300000,'15m':900000}[tf];opened=(start+step-1)//step*step
        for b in execution.bars(opened,tf):
            if b[0]>=until:break
            bars.append(b)
        covered=bool(opened==start and bars and bars[-1][1]+1>=until)
        candidate=dict(complete=covered,execution_tf=tf,initial_missing_minutes=(opened-start)/60000,horizons={})
        for minutes in (15,30,60,240):
            end=min(execution.until+1,start+minutes*60000);window=[b for b in bars if b[1]+1<=end]
            complete=bool(opened==start and window and window[-1][1]+1>=end and end==start+minutes*60000)
            high=max((b[3] for b in window),default=None)
            candidate['horizons'][str(minutes)]=dict(complete=complete,covered_minutes=len(window)*step/60000,reached_0_5_gross=bool(high and high>=trade['entry_open']*1.005),reached_1_gross=bool(high and high>=trade['entry_open']*1.01))
        if result is None or sum(h['covered_minutes'] for h in candidate['horizons'].values())>sum(h['covered_minutes'] for h in result['horizons'].values()):result=candidate
        if covered:break
    return result


def save(path,value):
    raw=json.dumps(value,separators=(',',':'),allow_nan=False).encode()
    temp=path.with_name(path.name+'.partial');temp.write_bytes(gzip.compress(raw,compresslevel=1,mtime=0) if path.suffix=='.gz' else raw);temp.replace(path)


def run(symbol):
    old=read(PREVIOUS/f'frozen_{symbol}_results.json.gz');packet=read(PREVIOUS/f'frozen_{symbol}_execution.json.gz')
    source_path=Path(old['source']['file']);assert hashlib.sha256(source_path.read_bytes()).hexdigest()==old['source']['file_sha256']
    source=unpack(read(source_path));full_rows=source['candles'];all_cases={c['signal_index']:c for c in old['case_traces'] if c['policy']=='agreed_regime_exits'}
    accepted={t['entry_time'] for t in old['variants']['peak_thresholds_with_plus']['replays']['agreed_regime_exits']['low_first']['trades']}
    indices=sorted(i for i,c in all_cases.items() if c['traces'][0]['entry_time'] in accepted)
    entries={i:entry_features(full_rows,i) for i in indices};rows,meta=prior.thin(source);del source,full_rows;gc.collect()
    execution=prior.Execution(symbol,rows,rows[-1]['close_time']);execution.cache.update(packet['blocks']);del packet
    policies={p.name:{order:[] for order in ('low_first','high_first')} for p in POLICIES}
    cases=[];observations={};fallbacks=Counter()
    try:
        for i in indices:
            entry=rows[i+1]['open_time'];old_traces=all_cases[i]['traces'];deadline=max(t['exit_time_upper'] for t in old_traces if t['status']=='CLOSED')
            fields=['feature.'+n for n in ('relative_volume','candle_range_atr','di_plus','di_minus','measurement_config_id')]
            five=strategy_memory.load(symbol,'5m',fields=fields,since=entry-24*STEP5,until=min(meta['observed_as_of'],deadline+STEP5),warmup=2)
            obs=Observations(five['candles'],entry,entries[i]['measurement_config_id']);observations[str(entry)]=dict(source_id=five['source_id'],memory=five['memory'],values=obs.values)
            selected_tf=None;matrix=None;reasons=[]
            for tf in ('1m','5m','15m'):
                first=next(execution.bars(entry,tf),None)
                if first is None or not math.isclose(first[2],rows[i+1]['open'],rel_tol=1e-9,abs_tol=1e-12):reasons.append(tf+': missing entry');continue
                matrix={p.name:[simulate(rows,i,execution,obs,entries[i],p,order,tf) for order in ('low_first','high_first')] for p in POLICIES}
                if any(t['status']=='EXECUTION_GAP' for traces in matrix.values() for t in traces) and tf!='15m':reasons.append(tf+': gap in at least one compared policy');continue
                selected_tf=tf;break
            assert matrix is not None;fallbacks[selected_tf]+=1
            for name,traces in matrix.items():
                for t in traces:policies[name][t['order']].append(t)
            # Future labels are diagnostic ONLY; the router never receives them.
            extended=[simulate(rows,i,execution,obs,entries[i],Policy('label_2gross',target=2),order,selected_tf) for order in ('low_first','high_first')]
            original=next(t for t in old_traces if t['order']=='low_first')
            recovery=post_stop(execution,original) if original['reason']=='HARD_STOP' else None
            labels={}
            for order,tr in zip(('low_first','high_first'),extended):
                quick=next(t for t in matrix['fixed_0_5_gross'] if t['order']==order)
                labels[order]='EXTENDED_2PCT' if tr.get('reason')=='TAKE_PROFIT' else 'ORDINARY_REBOUND' if tr['status']=='CLOSED' and quick.get('reason')=='TAKE_PROFIT' else 'FAILED_BEFORE_0_5' if quick.get('reason')=='HARD_STOP' else 'CENSORED'
            cases.append(dict(signal_index=i,entry_time=entry,features=entries[i],original=original,post_stop=recovery,labels=labels,label_traces=extended,execution_tf=selected_tf,fallback_reasons=reasons))
            print(json.dumps(dict(symbol=symbol,done=len(cases),total=len(indices),execution=selected_tf)),flush=True)
        result=dict(symbol=symbol,source=old['source'],first=old['first'],last=old['last'],entries=len(indices),policies={p.name:asdict(p) for p in POLICIES},
                    results={name:{order:dict(summary=summaries(trades),trades=trades) for order,trades in paths.items()} for name,paths in policies.items()},
                    cases=cases,common_execution_frames=dict(fallbacks),lower_timeframe_quality=dict(execution.quality))
        save(OUT/f'{symbol}_results.json.gz',result);save(OUT/f'{symbol}_5m_observations.json.gz',observations);save(OUT/f'{symbol}_execution.json.gz',dict(symbol=symbol,until=execution.until,blocks=execution.cache))
        return result
    finally:execution.close()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=dict(version='di50-breakout-exit-routing-v1',entry='Exactly the prior strict DI50 peak-turn entries: 38 BTC + 11 SUI on 15m; source hashes must match.',
                  costs=dict(fee_bps_per_side=4,slippage_bps_per_side=2),gross_definition='Reference/chart price rise from raw next-open entry, before fees and slippage. Net PnL includes both.',
                  initial_stop='0.5% net-loss budget remains active on every entry; actual adverse opens retained.',
                  policies=[asdict(p) for p in POLICIES],breakout_exit='After a gate known at the execution bar OPEN, cancel ordinary target permanently. +1% gross activates a 0.5% highest-since-entry trail; no additional Regime/DI+ gate.',
                  main_gate='5m close above prior 12 closed-bar highs, bullish close in upper 30%, stored relative_volume >=1.5 and candle_range_atr >=1.2. Current execution open must hold the broken level.',
                  diagnostic_gates='Entry: signal 15m close above previous high, upper30%, bullish, rvol>=1.5 and range/ATR>=1.2. Micro: 5m close above prior3 highs, bullish, upper40%.',
                  availability='Only closed 5m values known no later than execution-bar open. Missing/incompatible features do not fire the breakout gate and are counted in the observations. Mode selection is sticky. No later breakout retroactively cancels an earlier quick exit.',
                  protection='One sensitivity raises stop to net breakeven once price actually reaches +0.5% gross in selected-breakout mode. Before this point the initial stop remains. Gaps may still lose money.',
                  labels='2% gross before initial stop is a retrospective extended-move label, never an input. Post-stop rebound audits at 15/30/60/240 minutes are diagnostics, not held positions or exits.',
                  validation='Predefined simple gates, exploratory small sample; report all variants and chronological subperiods, not a fitted perfect classifier. No live trading changes.')
    save(OUT/'protocol.json',protocol)
    index={}
    for symbol in ('BTCUSDT','SUIUSDT'):
        r=run(symbol);index[symbol]={name:{order:payload['summary'] for order,payload in paths.items()} for name,paths in r['results'].items()}
        save(OUT/'summary.json',index);del r;gc.collect()


if __name__=='__main__':main()
