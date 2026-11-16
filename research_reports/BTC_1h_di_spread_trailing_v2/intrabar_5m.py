"""Forming 1h DI/RSI plus causally confirmed 5m DI-spread peaks.
No production feature/configuration, history or orders are written.
"""
from array import array
from bisect import bisect_right
from collections import Counter
import gzip,hashlib,json,math,sqlite3
from pathlib import Path
from Section_4_Features.features.momentum import calculate_dmi,calculate_rsi
from research_reports.BTC_1h_di_spread_trailing_v2 import replay as base

O=Path(__file__).parent
STEP=300000

def preview(state,high,low,close):
    atr,p,m,ph,pl,pc,gain,loss=state
    up=high-ph;down=pl-low
    tr=max(high-low,abs(high-pc),abs(low-pc))
    a=.1;atr=a*tr+(1-a)*atr
    p=a*(up if up>down and up>0 else 0)+(1-a)*p
    m=a*(down if down>up and down>0 else 0)+(1-a)*m
    d=close-pc;a=1/7
    gain=a*max(d,0)+(1-a)*gain;loss=a*max(-d,0)+(1-a)*loss
    rsi=math.nan if gain==loss==0 else 100. if loss==0 else 100-100/(1+gain/loss)
    return 100*p/atr,100*m/atr,rsi

def hourly_states(rows):
    dmi={};rsi={};states=[];compared=0;max_error=0.
    for row in rows:
        ready=all(dmi.get(k,{}).get('value') is not None for k in ('atr','plus','minus')) and all(rsi.get(k,{}).get('value') is not None for k in ('gain','loss'))
        states.append((dmi['atr']['value'],dmi['plus']['value'],dmi['minus']['value'],*dmi['previous'],rsi['gain']['value'],rsi['loss']['value']) if ready else None)
        dp,dm,_=calculate_dmi(dmi,row,10,10);rs=calculate_rsi(rsi,row['close'],7)
        pairs=[(dp,row['features']['di_plus']),(dm,row['features']['di_minus']),(rs,row['features']['rsi'])]
        if all(base.finite(a) and base.finite(b) for a,b in pairs):
            compared+=1;max_error=max(max_error,max(abs(a-b) for a,b in pairs))
    if max_error>1e-8:raise ValueError('Closed-hour kernel replay differs from frozen measurements')
    return states,dict(compared=compared,max_abs_error=max_error)

def load_five(until):
    path=O/'five_minute_source.json.gz'
    if path.exists():return json.loads(gzip.decompress(path.read_bytes()))
    from Section_1_Global_Core.memory_storage.Storage import klines_store
    conn=sqlite3.connect(klines_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1);rows=[];after=-1
    try:
        while True:
            block=conn.execute('SELECT open_time,close_time,open,high,low,close FROM klines WHERE symbol=? AND interval=? AND open_time>? AND close_time<=? ORDER BY open_time LIMIT 4096',('BTCUSDT','5m',after,until)).fetchall()
            if not block:break
            rows.extend([list(r) for r in block]);after=block[-1][0]
            if len(rows)%65536==0:print('freeze 5m',len(rows),flush=True)
    finally:conn.close()
    path.write_bytes(gzip.compress(json.dumps(rows,separators=(',',':')).encode(),compresslevel=1,mtime=0));return rows

class Peak:
    def __init__(self):self.previous=None;self.rising=False;self.last_time=None
    def step(self,point):
        stamp,plus,minus,rsi=point;result=None
        if self.previous is not None and stamp-self.last_time==STEP:
            old=abs(self.previous[1]-self.previous[2]);now=abs(plus-minus)
            if now>old:self.rising=True
            elif now<old:
                if self.rising and self.previous[2]>self.previous[1]:result=self.previous
                self.rising=False
        else:self.rising=False
        self.previous=point;self.last_time=stamp
        return result
    def reset(self):self.previous=None;self.rising=False;self.last_time=None

class PreviewContext:
    def __init__(self,rows,known,plus):self.hour=base.Context(rows);self.known=known;self.plus=plus
    def at(self,t):
        direction,_=self.hour.at(t);i=bisect_right(self.known,t)-1
        value=self.plus[i] if i>=0 and t-self.known[i]<STEP and math.isfinite(self.plus[i]) else None
        return direction,value

def make_signals(packet,bars):
    hours=packet['rows'];states,parity=hourly_states(hours);index={r['open_time']:i for i,r in enumerate(hours)}
    # Check lower- and higher-timeframe price consistency before interpreting a
    # forming hour. A mismatched or incomplete hour is excluded, never patched.
    groups={}
    for k,b in enumerate(bars):
        h=b[0]//base.HOUR*base.HOUR
        if h not in groups:groups[h]=[k,k+1,b[2],b[3],b[4],b[5],b[0],b[1],True]
        else:
            g=groups[h];g[8]=g[8] and b[0]==g[7]+1;g[1]=k+1;g[3]=max(g[3],b[3]);g[4]=min(g[4],b[4]);g[5]=b[5];g[7]=b[1]
    matched=set();mismatched=[]
    for h,g in groups.items():
        i=index.get(h)
        if i is None:continue
        r=hours[i]
        good=g[1]-g[0]==12 and g[6]==h and g[7]==h+base.HOUR-1 and g[8] and all(math.isclose(a,r[key],rel_tol=1e-7,abs_tol=.02) for a,key in zip(g[2:6],('open','high','low','close')))
        if good:matched.add(h)
        else:mismatched.append(h)
    known=array('q');plus_values=array('d');hpeak=Peak();fpeak=Peak();dmi5={};rsi5={};recent5=None;signals=[];aggregate=None;preview_error=0.;preview_compared=0
    for k,b in enumerate(bars):
        t,end,o,h,l,c=b;stamp=end+1;hour=t//base.HOUR*base.HOUR;i=index.get(hour)
        dp5,dm5,_=calculate_dmi(dmi5,dict(high=h,low=l,close=c),10,10);rs5=calculate_rsi(rsi5,c,7)
        five=fpeak.step((stamp,dp5,dm5,rs5)) if all(base.finite(x) for x in (dp5,dm5,rs5)) else None
        if five:recent5=(stamp,five)
        if aggregate is None or aggregate[0]!=hour:aggregate=[hour,o,h,l,c]
        else:aggregate[2]=max(aggregate[2],h);aggregate[3]=min(aggregate[3],l);aggregate[4]=c
        eligible=hour in matched and i is not None and states[i] is not None and not hours[i]['features'].get('measurement_gap')
        if not eligible:
            known.append(stamp);plus_values.append(math.nan);hpeak.reset();continue
        dp,dm,rs=preview(states[i],aggregate[2],aggregate[3],c)
        known.append(stamp);plus_values.append(dp)
        point=(stamp,dp,dm,rs);peak=hpeak.step(point)
        if end==hours[i]['close_time']:
            f=hours[i]['features'];expected=[f['di_plus'],f['di_minus'],f['rsi']]
            if all(base.finite(x) for x in expected):preview_error=max(preview_error,max(abs(a-z) for a,z in zip((dp,dm,rs),expected)));preview_compared+=1
        if k+1>=len(bars) or bars[k+1][0]!=stamp:continue
        common=dict(signal_time=t,known_time=stamp,entry_time=stamp,entry_open=bars[k+1][2],hour_index=i,entry_regime=None,preview_di_plus=dp,preview_di_minus=dm,preview_rsi=rs,preview_spread=abs(dp-dm),five_di_plus=dp5,five_di_minus=dm5,five_spread=abs(dp5-dm5),five_rsi=rs5)
        if peak and abs(peak[1]-peak[2])>40:
            evidence=dict(**common,method='forming_hour_first_drop',peak_di_minus=peak[2],peak_rsi=peak[3],peak_spread=abs(peak[1]-peak[2]))
            signals.append(evidence)
            if recent5 and stamp-recent5[0]<=2*STEP:signals.append({**evidence,'method':'forming_hour_drop_with_5m_peak','five_peak_known_time':recent5[0]})
        if five and dm>dp and dm-dp>40:
            signals.append(dict(**common,method='forming_hour_extreme_with_5m_peak',peak_di_minus=dm,peak_rsi=rs,peak_spread=dm-dp,five_peak_known_time=stamp))
    if preview_error>1e-8:raise ValueError('Forming-hour terminal previews differ from frozen 1h values')
    context=PreviewContext(hours,known,plus_values)
    for s in signals:s['entry_regime']=context.at(s['entry_time'])[0]
    quality=dict(closed_hour_kernel_parity=parity,terminal_preview_parity=dict(compared=preview_compared,max_abs_error=preview_error),raw_5m_candles=len(bars),matching_hour_count=len(matched),incomplete_or_mismatched_hour_count=len(mismatched),first_excluded_hours=mismatched[:12],raw_signals_by_method=dict(Counter(x['method'] for x in signals)))
    return signals,context,quality

def analyze(packet,bars,execution):
    signals,context,quality=make_signals(packet,bars);hours=packet['rows'];result=dict(version='btc-forming-1h-5m-confluence-v1',source_signature=packet['source_signature'],data_quality=quality,variants={},entry_cases=[],definition='Forming 1h RSI(7)/DI(10) evaluated at each closed 5m candle, without committing intermediate previews to hourly smoothing state. Confirmed 5m bearish DI-spread peak/drop is confluence; next-5m-open entry. Regime is latest closed Section5 1h output; bullish DI+ gate uses most recent 5m-confirmed forming-hour DI+ value. 0.5% hard stop and regime-dependent 1%-armed 0.5% trail; no timeout.')
    cache={};methods=['forming_hour_first_drop','forming_hour_drop_with_5m_peak','forming_hour_extreme_with_5m_peak']
    for method in methods:
      for threshold in (40,45,50):
       for rsi_mode in ('none','peak','signal'):
        chosen=[s for s in signals if s['method']==method and s['peak_di_minus']>threshold and (rsi_mode=='none' or (s['peak_rsi'] if rsi_mode=='peak' else s['preview_rsi'])<20)]
        eligible=[s for s in chosen if s['entry_regime'] in ('BEARISH','BULLISH')]
        key=f'{method}_di_minus_gt{threshold}_rsi_{rsi_mode}';variant=dict(raw_setups=len(chosen),eligible=len(eligible),regime_counts=dict(Counter(s['entry_regime'] for s in chosen)),replays={})
        for label,policy in [('price_stop',base.Policy()),('net_loss_budget',base.Policy(risk='net_0_5pct'))]:
            traces={'low_first':[],'high_first':[]}
            for s in eligible:
                identity=(s['entry_time'],policy)
                if identity not in cache:
                    # The common engine's default hour-index path is retained
                    # only as a fallback. All entry values are overridden here.
                    override={k:s[k] for k in ('signal_time','entry_time','entry_open','entry_regime')}
                    i=min(s['hour_index'],len(hours)-2)
                    cache[identity]=base.paired_trade(hours,i,execution,context,policy,override)
                for tr in cache[identity]:traces[tr['order']].append(tr)
            variant['replays'][label]={order:dict(independent=base.summarize(ts),single_position=base.portfolio(ts)) for order,ts in traces.items()}
        result['variants'][key]=variant
        print(key,variant['raw_setups'],json.dumps(variant['replays']['net_loss_budget']['low_first']['single_position']),flush=True)
    result['entry_cases']=[dict(entry_time=t,policy=p.__dict__,traces=traces) for (t,p),traces in cache.items()]
    result['signals']=signals
    result['limitations']=['5m confirmation does not identify the final future hourly extreme. Every local peak needs a prior observed increase; flat stretches after a decline do not fabricate new peaks.','5m DI-spread high is the interpretation of the user’s lower-timeframe high; no future price pivot is required.','Hours with incomplete/mismatched 5m OHLC are excluded for source consistency, not filled using later prices.','Minute/5m stop ordering remains an OHLC approximation; low-first/high-first scenarios are sensitivity cases, not exact tick replay.','Regime neutral/unknown entry periods are counted and skipped. The 0.5% net-budget scenario uses explicit fees/slippage and does not clip gap losses.']
    return result

if __name__=='__main__':
    packet=json.loads(gzip.decompress(base.SOURCE.read_bytes()));bars=load_five(packet['rows'][-1]['close_time'])
    frozen=O/'intrabar_execution_blocks.json.gz';cache=json.loads(gzip.decompress(frozen.read_bytes())) if frozen.exists() else json.loads(gzip.decompress((O/'execution_blocks.json.gz').read_bytes()))
    execution=base.Execution(packet['rows'][-1]['close_time'],cache)
    try:
        result=analyze(packet,bars,execution);raw=json.dumps(execution.cache,separators=(',',':'),allow_nan=False).encode();result['execution_source_sha256']=hashlib.sha256(raw).hexdigest();result['code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        (O/'intrabar_results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    finally:
        frozen.write_bytes(gzip.compress(json.dumps(execution.cache,separators=(',',':'),allow_nan=False).encode(),mtime=0));execution.close()
