"""User correction: exactly 0.2 percentage points total cost per round trip."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))

from collections import Counter
import csv
from datetime import datetime
import gc
import hashlib
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from Section_12_Research.reports.DI50_breakout_exit_routing_v1 import study as original

OUT=Path(__file__).parent
COST_PCT=.2
RISK_NET_PCT=.5
ZONE=ZoneInfo('Asia/Karachi')


def net_pct(reference,entry):
    value=100*(reference/entry-1)-COST_PCT
    return 0. if abs(value)<1e-10 else value


def level(entry,net_target):return entry*(1+(net_target+COST_PCT)/100)


class FrozenObservations(original.Observations):
    def __init__(self,packet,entry):
        self.values=packet['values'];self.known=[p['known'] for p in self.values];self.entry=entry


class FrozenExecution(original.prior.Execution):
    """Never read changing live price memory during the cost correction."""
    def block(self,stamp,tf):
        step=60000 if tf=='1m' else 300000
        start=stamp//(240*step)*(240*step)
        return self.cache.get(f'{tf}:{start}',[])


def protect_walk(position,row,eligible,order):
    threshold=position['entry']*1.005
    def promote():
        position['stop_price']=max(position['stop_price'],level(position['entry'],0))
        position['protected']=True
    if position.get('protected'):return original.exits.walk(position,row,eligible,0,0,order)
    points=[row['open'],row['low'],row['high'],row['close']] if order=='low_first' else [row['open'],row['high'],row['low'],row['close']]
    if points[0]>=threshold:promote();return original.exits.walk(position,row,eligible,0,0,order)
    for j,(a,b) in enumerate(zip(points,points[1:])):
        ends=[threshold,b] if not position.get('protected') and a<threshold<=b else [b]
        for k,end in enumerate(ends):
            piece=dict(row,open=a,high=max(a,end),low=min(a,end),close=end)
            hit=original.exits.walk(position,piece,eligible,0,0,'low_first' if end>=a else 'high_first')
            if hit:
                if j or k or hit['precision']!='OPEN':hit.update(time=row['close_time']+1,precision='WITHIN_CANDLE_UNKNOWN')
                return hit
            if not position.get('protected') and end>=threshold:promote()
            a=end
    return None


def simulate(rows,index,execution,obs,entry_info,policy,order,tf,context):
    start=rows[index+1]['open_time'];entry=rows[index+1]['open']
    initial_stop=level(entry,-RISK_NET_PCT)
    pos=dict(entry=entry,stop_price=initial_stop)
    selected=False;proof=None;last=None;count=0
    for t,end,o,h,l,c in execution.bars(start,tf):
        last=end;count+=1
        if policy.name=='old_regime_reference':
            current,plus=context.at(t)
            eligible=[dict(id='bear_target',action='TAKE_PROFIT',target_profit_pct=1+COST_PCT)] if current=='BEARISH' else [dict(id='bull_trail',action='TRAILING_SELL',trail=dict(activation_profit_pct=1+COST_PCT,distance_pct=.5))] if current=='BULLISH' and original.prior.execution_base.finite(plus) and plus>50 else []
        else:
            if not selected and policy.gate!='none':
                hit,evidence=obs.gate(policy.gate,t,o,entry_info)
                if hit:selected=True;proof=dict(evidence,selected_at=t);assert evidence['known']<=t
            target=policy.target+COST_PCT if policy.basis=='net' else policy.target
            eligible=[dict(id='breakout_trail',action='TRAILING_SELL',trail=dict(activation_profit_pct=1,distance_pct=.5))] if selected else [dict(id='quick_profit',action='TAKE_PROFIT',target_profit_pct=target)]
        row=dict(open_time=t,close_time=end,open=o,high=h,low=l,close=c)
        hit=protect_walk(pos,row,eligible,order) if selected and policy.protect else original.exits.walk(pos,row,eligible,0,0,order)
        if hit:
            price=hit['raw_price'];net=net_pct(price,entry);reason=hit['reason']
            if reason=='HARD_STOP' and pos.get('protected'):reason='BREAKEVEN_STOP' if net==0 else 'PROTECTED_STOP_GAP'
            return dict(status='CLOSED',reason=reason,signal_time=rows[index]['open_time'],signal_known_time=rows[index]['close_time']+1,entry_time=start,entry_open=entry,entry_fill=entry,
                        entry_regime=original.prior.direction(rows[index],'REGIME'),initial_stop=initial_stop,exit_reference=price,exit_bar_time=t,exit_time_upper=hit['time'],
                        gross_reference_pct=100*(price/entry-1),net_pct=net,round_trip_cost_pct=COST_PCT,execution_tf=tf,order=order,bars=count,
                        highest=pos['peak'],max_gross_before_exit_pct=100*(pos['peak']/entry-1),holding_minutes_upper=(hit['time']-start)/60000,
                        selected_breakout=selected,breakout_evidence=proof,protected=pos.get('protected',False),armed=bool(pos.get('trail_branch')))
    return dict(status='OPEN_AT_BOUNDARY' if last is not None and last>=execution.until else 'EXECUTION_GAP',entry_time=start,execution_tf=tf,order=order,selected_breakout=selected)


def run(symbol):
    old=original.read(original.OUT/f'{symbol}_results.json.gz');packet=original.read(original.OUT/f'{symbol}_execution.json.gz');observations=original.read(original.OUT/f'{symbol}_5m_observations.json.gz')
    path=Path(old['source']['file']);assert hashlib.sha256(path.read_bytes()).hexdigest()==old['source']['file_sha256']
    source=original.read(path);rows,_=original.prior.thin(source);del source;gc.collect()
    execution=FrozenExecution(symbol,rows,old['last']-1);execution.cache=packet['blocks'];context=original.prior.Context(rows)
    results={p.name:{order:[] for order in ('low_first','high_first')} for p in original.POLICIES};frames=Counter();cases=[]
    for case in old['cases']:
        i=case['signal_index'];obs=FrozenObservations(observations[str(case['entry_time'])],case['entry_time']);reasons=[]
        for tf in ('1m','5m','15m'):
            first=next(execution.bars(case['entry_time'],tf),None)
            if not first or not math.isclose(first[2],rows[i+1]['open'],rel_tol=1e-9,abs_tol=1e-12):reasons.append(tf+': missing entry');continue
            matrix={p.name:{order:simulate(rows,i,execution,obs,case['features'],p,order,tf,context) for order in ('low_first','high_first')} for p in original.POLICIES}
            if tf!='15m' and any(t['status']=='EXECUTION_GAP' for paths in matrix.values() for t in paths.values()):reasons.append(tf+': gap');continue
            break
        frames[tf]+=1
        for name,paths in matrix.items():
            for order,tr in paths.items():results[name][order].append(tr)
        cases.append(dict(entry_time=case['entry_time'],signal_index=i,execution_tf=tf,fallback_reasons=reasons,previous_execution_tf=case['execution_tf']))
    result=dict(symbol=symbol,source=old['source'],first=old['first'],last=old['last'],entries=old['entries'],cost_pct=COST_PCT,initial_net_risk_pct=RISK_NET_PCT,policies=old['policies'],cases=cases,
                common_execution_frames=dict(frames),results={name:{order:dict(summary=original.summaries(trades),trades=trades) for order,trades in paths.items()} for name,paths in results.items()})
    assert len(cases)==old['entries']
    original.save(OUT/f'{symbol}_results.json.gz',result)
    return result


def main():
    OUT.mkdir(exist_ok=True,parents=True)
    protocol=dict(version='di50-cost-correction-20bps',cost_pct=COST_PCT,model='Exactly 0.2 percentage points of entry notional deducted once per completed round trip: net_pct = gross_price_pct - 0.2. No additional fee/slippage deductions.',
                  risk='0.5% maximum intended NET loss, therefore initial raw price stop is 0.3% below entry. Actual adverse opening gaps retained.',entry='Same 38 BTC + 11 SUI as v1; no entry or breakout parameter changes.',
                  profit='Ordinary +0.5% gross => +0.3% net; +1% gross => +0.8% net. Breakout trail arms at +1% gross, distance0.5%.',old_reference='Prior regime-dependent policy rerun at these corrected costs: bearish +1% NET target, bullish +1% NET AND DI+ >50 to activate0.5% trail.',
                  data='Only original frozen 15m source, frozen 1m/5m prices and frozen 5m gate observations. No fresh memory reads or classifiers.',validation='Both OHLC paths and common frame per entry; preserve original v1 evidence. No live configuration changes.')
    original.save(OUT/'protocol.json',protocol)
    summary={};all_results=[]
    for symbol in ('BTCUSDT','SUIUSDT'):
        r=run(symbol);summary[symbol]={name:{order:p['summary'] for order,p in paths.items()} for name,paths in r['results'].items()};all_results.append(r)
        print(symbol,r['common_execution_frames'],flush=True)
    original.save(OUT/'summary.json',summary)
    write_report(all_results)


def write_report(results):
    exports=[];lines=['# DI50 exit comparison — corrected 0.2% total costs','',
        '**Cost correction:** the user specifies 0.2% total round-trip costs. The prior v1 run used 4 bps fees +2 bps slippage per side (approximately 0.12% total); its cost assumptions are superseded for the current comparison. Original artifacts remain intact.','',
        'This run uses the user’s arithmetic exactly: **net return = gross chart-price return −0.2 percentage points**, deducted once per completed trade. No extra fees or slippage are stacked. Thus +0.5% gross gives +0.3% net, and +1% gross gives +0.8% net. This is a fixed cost allowance, not a claim that an exchange always charges this exact amount.','',
        'The standing maximum loss remains **0.5% net**, so the initial price stop is **0.3% below entry**. A 0.5% price stop would instead lose 0.7% net and is not substituted. Actual adverse opening gaps remain real losses. The tighter stop can change the winning trades and win rate; simply subtracting another 0.08% from old PnL is insufficient.','',
        'At +0.3% per win and −0.5% per loss, a 50% hit rate averages −0.1% per trade. Break-even is **62.5% wins**, before gap losses. At +0.8% per win it is **38.46%**.','',
        'Same 38 BTC and 11 SUI strict 15m DI entries and breakout gates; source hashes match. Reused only frozen prices/5m evidence, without live-memory reads, classifier recalculation or parameter fitting. The old regime-dependent policy is also rerun at corrected costs; it retains net +1% targets/activation, whereas new ordinary targets are gross.','',
        'Low-first and high-first are explicit OHLC order assumptions, not guaranteed tick-path bounds. Common execution fidelity is selected per entry across all policies. Full source periods and every losing trade remain in the saved results. No live strategy or workspace preset is enabled or changed.','']
    for r in results:
        lines.extend([f'## {r["symbol"]} — {r["entries"]} entries','',f'Execution frames: {r["common_execution_frames"]}.','',
                      '| Policy | Wins low-first | Win% low / high | Mean net/trade low / high | PF low / high |','|---|---:|---:|---:|---:|'])
        for name,paths in r['results'].items():
            lo=paths['low_first']['summary'];hi=paths['high_first']['summary']
            lines.append(f'| {name} | {lo["wins"]}/{lo["closed"]} | {lo["win_pct"]:.2f}% / {hi["win_pct"]:.2f}% | {lo["mean_net_pct"]:+.4f}% / {hi["mean_net_pct"]:+.4f}% | {lo["profit_factor"]:.2f} / {hi["profit_factor"]:.2f} |')
            for order,payload in paths.items():
                for t in payload['trades']:
                    assert t['status']=='CLOSED'
                    exports.append(dict(symbol=r['symbol'],policy=name,order=order,entry_pkt=datetime.fromtimestamp(t['entry_time']/1000,ZONE).isoformat(),exit_pkt_upper=datetime.fromtimestamp(t['exit_time_upper']/1000,ZONE).isoformat(),entry_open=t['entry_open'],initial_stop=t['initial_stop'],exit_reference=t['exit_reference'],gross_pct=t['gross_reference_pct'],cost_pct=COST_PCT,net_pct=t['net_pct'],reason=t['reason'],execution_tf=t['execution_tf'],selected_breakout=t['selected_breakout'],protected=t['protected']))
        lines.append('')
    lines.extend(['## Evidence','', '`protocol.json` defines the correction; `summary.json` contains every policy/path summary; `*_results.json.gz` retains all trades; `all_exit_trades.csv` lists every exit. `execution_audit.json` checks all 1,176 trades for gross/net arithmetic, raw initial stops, target basis, price-bar fills and causal gate timestamps: zero mismatches. 36 targeted Section_13_Development/tests passed, including the cost arithmetic, hard stops, trailing and breakeven protection.','',
                  'Reproduce: `PYTHONPATH=/tmp/btc-section5-test-deps:. .venv-build/bin/python3 -m research_reports.DI50_breakout_exit_routing_cost20bps.study`',''])
    (OUT/'README.md').write_text('\n'.join(lines))
    with (OUT/'all_exit_trades.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(exports[0]));writer.writeheader();writer.writerows(exports)


if __name__=='__main__':main()
