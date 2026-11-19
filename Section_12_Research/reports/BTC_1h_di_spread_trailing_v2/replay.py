"""BTC 1h setup; recorded 1m/5m hard-stop and regime-dependent trailing replay.
Read-only market input; never emits production decisions or exchange orders.
"""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))

from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from datetime import datetime,timezone
import gzip,hashlib,json,math,sqlite3,statistics
from pathlib import Path

OUT=Path(__file__).parent
SOURCE=OUT.parent/'BTC_1h_di_spread_reversal/source.json.gz'
MINUTE=60000
HOUR=60*MINUTE
FEE=.0004
SLIP=.0002

def utc(ms):return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def abs_spread(r):return abs(r['features']['di_minus']-r['features']['di_plus'])
def valid(r):
    f=r['features'];return not f.get('measurement_gap') and all(finite(f.get(k)) for k in ('di_plus','di_minus','rsi'))
def regime(r):
    c=r['context']['REGIME'];return c['classification'].get('direction','UNKNOWN') if c['data_quality'] in ('VALID','PARTIAL') else 'UNKNOWN'
def setup(rows,i,threshold,kind):
    if i<2 or i+1>=len(rows):return False
    a,b,c=rows[i-2:i+1]
    if not all(valid(r) for r in (a,b,c)):return False
    if any(x['close_time']+1!=y['open_time'] for x,y in zip((a,b,c), (b,c,rows[i+1]))):return False
    fa,fb,fc=(r['features'] for r in (a,b,c));sa,sb,sc=(abs_spread(r) for r in (a,b,c))
    if not (fb['di_minus']>fb['di_plus'] and sb>40 and sb>=sa and sc<sb):return False
    f=fc if kind.startswith('confirmation') else fb
    if f['di_minus']<=threshold:return False
    if kind.startswith('confirmation') and not (fc['di_minus']>fc['di_plus'] and sc>40):return False
    if kind.endswith('rsi_at_peak') and fb['rsi']>=20:return False
    if kind.endswith('rsi_at_signal') and fc['rsi']>=20:return False
    return True

@dataclass(frozen=True)
class Policy:
    risk:str='price_0_5pct' # alternate: target net loss 0.5% including assumed costs
    activation:str='net_1pct'
    regime_mode:str='dynamic'
    fee:float=FEE
    slip:float=SLIP
    trail:float=.005

def net(reference,entry_fill,policy):return (reference*(1-policy.slip)*(1-policy.fee)/(entry_fill*(1+policy.fee))-1)*100

def levels(entry_open,policy):
    entry_fill=entry_open*(1+policy.slip)
    hard=entry_fill*.995 if policy.risk=='price_0_5pct' else entry_fill*(1+policy.fee)*.995/((1-policy.slip)*(1-policy.fee))
    trigger=entry_fill*1.01 if policy.activation=='price_1pct' else entry_fill*(1+policy.fee)*1.01/((1-policy.slip)*(1-policy.fee))
    return entry_fill,hard,trigger

class Context:
    def __init__(self,rows):self.rows=rows;self.known=[r['close_time']+1 for r in rows]
    def at(self,stamp):
        i=bisect_right(self.known,stamp)-1
        if i<0:return ('UNKNOWN',None)
        r=self.rows[i]
        if stamp-(r['close_time']+1)>=HOUR:return ('UNKNOWN',None)
        return regime(r),r['features']['di_plus']

class Execution:
    """Small indexed raw reads; cache and freeze every used block for reproducibility."""
    def __init__(self,until,cache=None):
        from Section_1_Global_Core.memory_storage.Storage import klines_store
        self.until=until;self.cache=cache or {};self.path=klines_store.DB_PATH;self.conn=None
    def block(self,stamp,tf):
        step=MINUTE if tf=='1m' else 5*MINUTE;start=stamp//(256*step)*(256*step);key=f'{tf}:{start}'
        if key not in self.cache:
            if self.conn is None:self.conn=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.5)
            # fetchall ends the source read before interpreting any prices.
            self.cache[key]=[list(r) for r in self.conn.execute('SELECT open_time,close_time,open,high,low,close FROM klines WHERE symbol=? AND interval=? AND open_time>=? AND open_time<? AND close_time<=? ORDER BY open_time',('BTCUSDT',tf,start,start+256*step,self.until)).fetchall()]
        return self.cache[key]
    def bars(self,start,tf):
        step=MINUTE if tf=='1m' else 5*MINUTE;stamp=start
        while stamp+step-1<=self.until:
            block=self.block(stamp,tf);selected=[r for r in block if r[0]>=stamp]
            if not selected or selected[0][0]!=stamp:return
            for r in selected:
                if r[0]!=stamp or r[1]!=stamp+step-1:return
                yield r;stamp+=step
    def close(self):
        if self.conn:self.conn.close()


def trade(hour_rows,i,execution,contexts,policy,order,tf,entry_override=None):
    override=entry_override or {}
    start=override.get('entry_time',hour_rows[i+1]['open_time']);expected=override.get('entry_open',hour_rows[i+1]['open']);entry_regime=override.get('entry_regime',regime(hour_rows[i]));signal_stamp=override.get('signal_time',hour_rows[i]['open_time']);entry_fill,hard,trigger=levels(expected,policy)
    bear_target=entry_fill*1.01 if getattr(policy,'bearish_target_basis',policy.activation)=='price_1pct' else entry_fill*(1+policy.fee)*1.01/((1-policy.slip)*(1-policy.fee))
    high=entry_fill;armed=False;armed_time=None;arm_regime=None;last=None;bars=0;unknown_context=0;ambiguous=False
    def finish(reason,reference,bar,*,at_open=False):
        return dict(status='CLOSED',reason=reason,signal_time=signal_stamp,entry_time=start,entry_open=expected,entry_fill=entry_fill,hard_stop=hard,activation_price=trigger,take_profit_price=bear_target if getattr(policy,'bearish_exit','trail')=='fixed_target' else None,exit_bar_time=bar[0],exit_time_upper=bar[0] if at_open else bar[1]+1,exit_reference=reference,net_pct=net(reference,entry_fill,policy),price_pct=(reference/entry_fill-1)*100,entry_regime=entry_regime,arm_regime=arm_regime,armed=armed,armed_time=armed_time,highest=high,bars=bars,execution_tf=tf,order=order,ambiguous_stop_bar=ambiguous,unknown_context_bars=unknown_context,holding_minutes_upper=((bar[0] if at_open else bar[1]+1)-start)/MINUTE)
    for bar in execution.bars(start,tf):
        t,end,o,h,l,c=bar;bars+=1;last=bar
        if not all(finite(p) and p>0 for p in (o,h,l,c)) or not l<=min(o,c)<=max(o,c)<=h:break
        if bars==1 and not math.isclose(o,expected,rel_tol=1e-7,abs_tol=.02):
            return dict(status='ENTRY_PRICE_MISMATCH',entry_time=start,entry_regime=entry_regime,execution_tf=tf,actual_open=o,expected_open=expected,order=order)
        current_regime,plus=contexts.at(t)
        if policy.regime_mode=='entry':current_regime=entry_regime
        if current_regime not in ('BULLISH','BEARISH'):unknown_context+=1
        gate=current_regime=='BEARISH' or current_regime=='BULLISH' and finite(plus) and plus>50
        # Stops already active before the opening tick get the actual gap price.
        active_stop=max(hard,high*(1-policy.trail)) if armed else hard
        if o<=active_stop:return finish('TRAILING_STOP' if armed and active_stop>hard else 'HARD_STOP',o,bar,at_open=True)
        points=(o,h,l,c) if order=='high_first' else (o,l,h,c)
        previous=o
        for k,price in enumerate(points):
            old_high=high;high=max(high,price)
            if current_regime=='BEARISH' and getattr(policy,'bearish_exit','trail')=='fixed_target' and price>=bear_target:
                return finish('TAKE_PROFIT',bear_target,bar,at_open=k==0)
            if not armed and gate and price>=trigger:
                armed=True;armed_time=t;arm_regime=current_regime
            stop=max(hard,high*(1-policy.trail)) if armed else hard
            if armed and high>old_high and l<=stop and h>=trigger:ambiguous=True
            # A late DI+/regime gate may activate below the highest-since-entry
            # trail. That is an immediate market exit at current price, never a
            # fictional fill back up at a stop price above the market.
            if price<=stop:
                reference=stop if k>0 and previous>stop>=price else price
                return finish('TRAILING_STOP' if armed and stop>hard else 'HARD_STOP',reference,bar,at_open=k==0)
            previous=price
    complete_to_boundary=last is not None and last[1]>=execution.until
    mark=net(last[5],entry_fill,policy) if last else None
    return dict(status='OPEN_AT_BOUNDARY' if complete_to_boundary else 'EXECUTION_GAP',signal_time=signal_stamp,entry_time=start,entry_regime=entry_regime,armed=armed,armed_time=armed_time,execution_tf=tf,order=order,bars=bars,last_bar_time=last[0] if last else None,last_known_mtm_pct=mark,unknown_context_bars=unknown_context)


def paired_trade(rows,i,execution,contexts,policy,entry_override=None):
    first=[trade(rows,i,execution,contexts,policy,order,'1m',entry_override) for order in ('low_first','high_first')]
    if any(x['status'] in ('EXECUTION_GAP','ENTRY_PRICE_MISMATCH') for x in first):
        fallback=[trade(rows,i,execution,contexts,policy,order,'5m',entry_override) for order in ('low_first','high_first')]
        for x in fallback:x['fallback_reason_1m']=[y['status'] for y in first]
        return fallback
    return first


def summarize(trades):
    closed=[x for x in trades if x['status']=='CLOSED'];returns=[x['net_pct'] for x in closed];positive=sum(x>0 for x in returns);profit=sum(x for x in returns if x>0);loss=-sum(x for x in returns if x<0)
    return dict(entries=len(trades),closed=len(closed),unresolved=len(trades)-len(closed),wins=positive,win_pct=100*positive/len(closed) if closed else None,mean_net_pct=statistics.mean(returns) if returns else None,median_net_pct=statistics.median(returns) if returns else None,profit_factor=profit/loss if loss else None,sum_trade_net_pct=sum(returns),worst_net_pct=min(returns,default=None),best_net_pct=max(returns,default=None),median_holding_minutes=statistics.median(x['holding_minutes_upper'] for x in closed) if closed else None,max_holding_minutes=max((x['holding_minutes_upper'] for x in closed),default=None),trail_armed=sum(x.get('armed',False) for x in trades),exit_reasons=dict(Counter(x.get('reason',x['status']) for x in trades)),execution_frames=dict(Counter(x['execution_tf'] for x in trades)),ambiguous_stop_bars=sum(x.get('ambiguous_stop_bar',False) for x in closed),loss_exceeds_net_0_5pct=sum(x<-.5000001 for x in returns),open_positions=[x for x in trades if x['status']!='CLOSED'])


def portfolio(trades):
    accepted=[];blocked=-1;skipped=0;unpriced=0
    for tr in trades:
        if tr['entry_time']<blocked:skipped+=1;continue
        if tr['status']=='ENTRY_PRICE_MISMATCH':unpriced+=1;continue
        accepted.append(tr)
        if tr['status']!='CLOSED':blocked=math.inf
        else:blocked=tr['exit_time_upper']
    result=summarize(accepted);equity=peak=1.;dd=0.
    for tr in accepted:
        if tr['status']!='CLOSED':continue
        equity*=1+tr['net_pct']/100;peak=max(peak,equity);dd=min(dd,(equity/peak-1)*100)
    return dict(**result,overlap_skipped=skipped,unpriced_entries_skipped=unpriced,closed_equity_return_pct=(equity-1)*100,closed_equity_max_drawdown_pct=dd,account_return_complete=not unpriced and all(x['status']=='CLOSED' for x in accepted))


def analyze(packet,execution):
    rows=packet['rows'];contexts=Context(rows)
    kinds=['peak_no_rsi','peak_rsi_at_peak','peak_rsi_at_signal','confirmation_no_rsi','confirmation_rsi_at_signal']
    result=dict(version='btc-di-spread-trailing-v2',source_signature=packet['source_signature'],coverage=dict(candles=len(rows),first=rows[0]['open_time'],last_closed=rows[-1]['close_time']),policies={},variants={},signal_funnel={},entry_cases={},assumptions=dict(fee_bps_per_side=4,slippage_bps_per_side=2,hard_stop='0.5% price from entry fill; separate 0.5% net-budget sensitivity',profit_trigger='1% net after assumed round-trip costs; separate 1% price sensitivity',trail='0.5% below highest observed since entry, active only after gate; never disarm',bearish_gate='current net profit >=1%',bullish_gate='current net profit >=1% AND latest closed-hour DI+ >50',regime='current latest fully closed Section5 REGIME direction; neutral/unknown entries skipped; unknown while holding does not arm a new trail; hard/armed stops remain active',execution='Closed-hour setup, next-hour open entry. Recorded 1m prices where continuous; rerun from entry on 5m only if 1m missing. No fixed target sale, timeout, averaging down or invented tick ordering.'))
    usable_count=sum(valid(x) for x in rows);raw_peak_count=0;over40=0
    for i in range(2,len(rows)-1):
        a,b,c=rows[i-2:i+1]
        if not all(valid(x) for x in (a,b,c)) or any(x['close_time']+1!=y['open_time'] for x,y in zip((a,b,c),(b,c,rows[i+1]))):continue
        if b['features']['di_minus']>b['features']['di_plus'] and abs_spread(b)>=abs_spread(a) and abs_spread(c)<abs_spread(b):
            raw_peak_count+=1;over40+=abs_spread(b)>40
    result['signal_funnel']=dict(usable_candles=usable_count,bearish_local_spread_first_drops=raw_peak_count,peak_spread_gt40=over40)
    cache={}
    for threshold in (40,45,50):
        for kind in kinds:
            indices=[i for i in range(2,len(rows)-1) if setup(rows,i,threshold,kind)]
            eligible=[i for i in indices if regime(rows[i]) in ('BEARISH','BULLISH')]
            key=f'di_minus_gt{threshold}_{kind}';variant=dict(raw_setups=len(indices),regime_counts=dict(Counter(regime(rows[i]) for i in indices)),eligible_entries=len(eligible),year_counts=dict(Counter(utc(rows[i]['open_time'])[:4] for i in indices)),replays={})
            policies=dict(primary=Policy(),net_loss_budget=Policy(risk='net_0_5pct'),price_profit_trigger=Policy(activation='price_1pct'),entry_regime_frozen=Policy(regime_mode='entry'))
            for policy_name,policy in policies.items():
                result['policies'][policy_name]=policy.__dict__;traces={'low_first':[],'high_first':[]}
                for i in eligible:
                    identity=(i,policy)
                    if identity not in cache:cache[identity]=paired_trade(rows,i,execution,contexts,policy)
                    for tr in cache[identity]:traces[tr.get('order','low_first')].append(tr)
                # Unresolved records also retain the chosen ordering.
                item=dict(scenarios={})
                for order,trades in traces.items():
                    item['scenarios'][order]=dict(independent=summarize(trades),single_position=portfolio(trades),by_entry_regime={label:summarize([t for t in trades if t['entry_regime']==label]) for label in ('BEARISH','BULLISH')},by_period={label:summarize([t for t in trades if ('2017_2023' if t['entry_time']<1704067200000 else '2024' if t['entry_time']<1735689600000 else '2025_2026')==label]) for label in ('2017_2023','2024','2025_2026')})
                item['ordering_changed_closed_result']=sum(a.get('net_pct')!=b.get('net_pct') or a['status']!=b['status'] for a,b in zip(traces['low_first'],traces['high_first']))
                variant['replays'][policy_name]=item
            result['variants'][key]=variant
            print(key,variant['raw_setups'],json.dumps(variant['replays']['primary']['scenarios']['low_first']['single_position']),flush=True)
    # Keep each distinct entry/policy/order audit once, rather than repeating it
    # in all overlapping signal variants.
    result['entry_cases']=[dict(signal_index=i,policy=p.__dict__,traces=traces) for (i,p),traces in cache.items()]
    result['limitations']=['1m/5m OHLC still lacks tick order. Low-first/high-first are explicit sensitivity paths, not guaranteed bounds over every possible intrabar oscillation. Same-bar arm/ratchet/stop cases remain flagged.','A 0.5% price stop is not a 0.5% net loss cap after fees/slippage; the cost-adjusted sensitivity targets -0.5% under assumed fills. Gap openings can breach either intended cap.','Regime and DI+ use only the last closed hour. Current Section5 definitions are reconstructed offline, not original live publication.','Unknown/neutral entry regimes are counted and skipped, not silently treated as bearish. An unresolved trade keeps capital occupied in the single-position replay.','All thresholds were user-specified. These are historical research results, not a prospective validation or live deployment.']
    return result

if __name__=='__main__':
    packet=json.loads(gzip.decompress(SOURCE.read_bytes()));frozen=OUT/'execution_blocks.json.gz'
    existing=json.loads(gzip.decompress(frozen.read_bytes())) if frozen.exists() else {}
    execution=Execution(packet['rows'][-1]['close_time'],existing)
    try:
        result=analyze(packet,execution)
        raw=json.dumps(execution.cache,separators=(',',':'),allow_nan=False).encode();frozen.write_bytes(gzip.compress(raw,mtime=0));result['execution_source_sha256']=hashlib.sha256(raw).hexdigest()
        (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    finally:
        # Preserve bounded read blocks even if a research assertion interrupts a
        # run; subsequent checks need not repeat reads against the live source.
        raw=json.dumps(execution.cache,separators=(',',':'),allow_nan=False).encode();frozen.write_bytes(gzip.compress(raw,mtime=0))
        execution.close()
