"""Independent price-segment replay of every new exit, using frozen evidence."""
from bisect import bisect_right
from collections import Counter
import math
from . import study as s


def replay(bars,policy,observations,entry_info,entry_time,order):
    # Deliberately do not call strategy_exits.walk/trigger_price or study.simulate.
    raw_entry=bars[0][2];paid=raw_entry*(1+s.SLIP)*(1+s.FEE)
    hard=paid*.995/((1-s.SLIP)*(1-s.FEE));peak=raw_entry
    target=raw_entry*(1+policy['target']/100) if policy['basis']=='gross' else paid*(1+policy['target']/100)/((1-s.SLIP)*(1-s.FEE))
    selected=armed=protected=False;selected_at=None;known=[p['known'] for p in observations]

    def answer(price,t,reason):
        value=(price*(1-s.SLIP)*(1-s.FEE)/paid-1)*100
        if abs(value)<1e-10:value=0.
        if reason=='HARD_STOP' and protected:reason='BREAKEVEN_STOP' if value==0 else 'PROTECTED_STOP_GAP'
        return dict(exit_reference=price,exit_time_upper=t,reason=reason,net_pct=value,highest=peak,
                    selected_breakout=selected,selected_at=selected_at,protected=protected,armed=armed)

    for opened,closed,o,h,l,c in bars:
        gate=policy['gate']
        if not selected and gate!='none':
            j=bisect_right(known,opened)-1;p=observations[j] if j>=0 and opened-known[j]<s.STEP5 else {}
            hit=gate=='all' or gate=='entry_expansion' and entry_info['entry_expansion']
            if gate in ('micro_reclaim','volume_breakout'):
                level=p.get('micro_level' if gate=='micro_reclaim' else 'volume_level',math.inf)
                hit=bool(p.get('ready') and p.get(gate) and o>=level)
            if hit:selected=True;selected_at=opened
        if selected and policy['protect'] and o>=raw_entry*1.005:
            protected=True;hard=max(hard,paid/((1-s.SLIP)*(1-s.FEE)))
        stop=max(hard,peak*.995) if armed else hard
        if o<=stop:return answer(o,opened,'TRAILING_STOP' if armed and peak*.995>hard else 'HARD_STOP')
        if not selected and o>=target:peak=max(peak,target);return answer(target,opened,'TAKE_PROFIT')
        if selected and not armed and o>=raw_entry*1.01:
            armed=True;peak=max(peak,o)
            if o<=max(hard,peak*.995):return answer(o,opened,'TRAILING_STOP' if peak*.995>hard else 'HARD_STOP')
        peak=max(peak,o)
        points=[o,l,h,c] if order=='low_first' else [o,h,l,c]
        for a,b in zip(points,points[1:]):
            if b<a:
                stop=max(hard,peak*.995) if armed else hard
                if b<=stop:return answer(stop,closed+1,'TRAILING_STOP' if armed and peak*.995>hard else 'HARD_STOP')
            else:
                if not selected and b>=target:peak=max(peak,target);return answer(target,closed+1,'TAKE_PROFIT')
                if selected and policy['protect'] and not protected and b>=raw_entry*1.005:
                    protected=True;hard=max(hard,paid/((1-s.SLIP)*(1-s.FEE)))
                if selected and not armed and b>=raw_entry*1.01:
                    activated=max(a,raw_entry*1.01);peak=max(peak,activated);armed=True
                    if activated<=max(hard,peak*.995):return answer(activated,closed+1,'TRAILING_STOP' if peak*.995>hard else 'HARD_STOP')
            peak=max(peak,b)
    raise AssertionError('Frozen execution ended before this closed trade')


def main():
    counts=Counter()
    for symbol in ('BTCUSDT','SUIUSDT'):
        r=s.read(s.OUT/f'{symbol}_results.json.gz');packet=s.read(s.OUT/f'{symbol}_execution.json.gz');obs=s.read(s.OUT/f'{symbol}_5m_observations.json.gz')
        old=s.read(s.PREVIOUS/f'frozen_{symbol}_results.json.gz')
        previous={t['entry_time']:c['traces'] for c in old['case_traces'] if c['policy']=='agreed_regime_exits' for t in c['traces']}
        cases={c['entry_time']:c for c in r['cases']}
        blocks={tf:{b[0]:b for key,block in packet['blocks'].items() if key.startswith(tf+':') for b in block} for tf in ('1m','5m')}
        for name,paths in r['results'].items():
            for order,payload in paths.items():
                assert len(payload['trades'])==r['entries'] and payload['summary']['overlap_skipped']==0
                for trade in payload['trades']:
                    assert trade['status']=='CLOSED' and trade['entry_time'] in cases
                    assert trade['signal_known_time']<=trade['entry_time']
                    if name=='old_regime_reference':
                        expected=next(t for t in previous[trade['entry_time']] if t['order']==order)
                        for key in ('exit_reference','exit_time_upper','net_pct','reason','highest'):assert trade[key]==expected[key],(symbol,key)
                        counts['unchanged_original_trades']+=1;continue
                    frame=trade['execution_tf'];step={'1m':60000,'5m':300000}[frame]
                    bars=[blocks[frame][t] for t in range(trade['entry_time'],trade['exit_bar_time']+1,step)]
                    expected=replay(bars,r['policies'][name],obs[str(trade['entry_time'])]['values'],cases[trade['entry_time']]['features'],trade['entry_time'],order)
                    for key in ('exit_reference','exit_time_upper','reason','net_pct','highest','selected_breakout','protected','armed'):
                        actual=trade[key];want=expected[key]
                        same=math.isclose(actual,want,rel_tol=1e-10,abs_tol=1e-9) if isinstance(actual,(float,int)) and not isinstance(actual,bool) else actual==want
                        assert same,(symbol,name,order,trade['entry_time'],key,actual,want)
                    if trade['selected_breakout']:
                        proof=trade['breakout_evidence'];assert proof['known']<=proof['selected_at']==expected['selected_at']<=trade['exit_time_upper']
                        counts['causal_route_checks']+=1
                    counts['independent_exit_replays']+=1
        counts[symbol+'_entries']=r['entries']
    s.save(s.OUT/'independent_execution_audit.json',dict(counts=counts,mismatches=0,method='Separate monotonic price-segment engine; no production/research walk helper. Frozen gate observations are inputs, not independently recomputed indicators. Exact original-cohort replay checked separately.'))
    print(dict(counts=counts,mismatches=0))


if __name__=='__main__':main()
