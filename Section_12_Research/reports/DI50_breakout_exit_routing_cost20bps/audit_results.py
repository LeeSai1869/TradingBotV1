"""Independent arithmetic, standing-stop and recorded-price audit for cost correction."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))

from collections import Counter
import math
from . import study as s


def close(a,b):return math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-9)


def main():
    counts=Counter()
    for symbol in ('BTCUSDT','SUIUSDT'):
        r=s.original.read(s.OUT/f'{symbol}_results.json.gz');old=s.original.read(s.original.OUT/f'{symbol}_results.json.gz')
        packet=s.original.read(s.original.OUT/f'{symbol}_execution.json.gz')
        bars={frame:{bar[0]:bar for key,block in packet['blocks'].items() if key.startswith(frame+':') for bar in block} for frame in ('1m','5m')}
        cohort=[c['entry_time'] for c in old['cases']]
        assert [c['entry_time'] for c in r['cases']]==cohort
        assert r['common_execution_frames']==old['common_execution_frames']
        for name,paths in r['results'].items():
            policy=r['policies'][name]
            for order,payload in paths.items():
                assert [t['entry_time'] for t in payload['trades']]==cohort
                assert payload['summary']['unresolved']==0 and payload['summary']['overlap_skipped']==0
                for t in payload['trades']:
                    assert t['status']=='CLOSED' and t['signal_known_time']<=t['entry_time']<=t['exit_time_upper']
                    entry=t['entry_open'];exit=t['exit_reference'];hard=entry*.997
                    assert close(t['initial_stop'],hard)
                    assert close(t['gross_reference_pct'],100*(exit-entry)/entry)
                    assert close(t['net_pct'],100*(exit-entry)/entry-.2)
                    assert close(t['round_trip_cost_pct'],.2)
                    frame=t['execution_tf'];bar=bars[frame][t['exit_bar_time']]
                    assert t['exit_time_upper'] in (bar[0],bar[1]+1)
                    reason=t['reason']
                    if reason=='TAKE_PROFIT':
                        gross=1.2 if name=='old_regime_reference' else policy['target']+(.2 if policy['basis']=='net' else 0)
                        target=entry*(1+gross/100)
                        assert close(exit,target) and bar[3]>=target*(1-1e-10)
                        counts['target_basis_checks']+=1
                    else:
                        assert bar[4]*(1-1e-10)<=exit<=bar[3]*(1+1e-10)
                    if reason=='HARD_STOP':
                        assert close(exit,hard) or close(exit,bar[2]) and bar[2]<hard
                        assert t['net_pct']<=-.5+1e-8
                    if reason=='BREAKEVEN_STOP':
                        assert t['protected'] and close(exit,entry*1.002) and close(t['net_pct'],0)
                    if reason=='TRAILING_STOP':
                        trailing=t['highest']*.995
                        activation=entry*(1.012 if name=='old_regime_reference' else 1.01)
                        assert t['armed'] and t['highest']>=activation*(1-1e-10)
                        assert close(exit,trailing) or close(exit,bar[2]) and exit<=trailing or close(exit,activation) and exit<=trailing
                    if t['net_pct']<-.5-1e-8:
                        assert close(exit,bar[2]) and exit<hard
                        counts['retained_gap_breaches']+=1
                    if t['selected_breakout']:
                        proof=t['breakout_evidence'];assert proof['known']<=proof['selected_at']<=t['exit_time_upper']
                        counts['causal_route_checks']+=1
                    counts['closed_trades_checked']+=1
        counts[symbol+'_entries']=len(cohort)
    evidence=dict(counts=counts,mismatches=0,method='Independent arithmetic and frozen exit-bar validation, source/cohort/fidelity parity, raw initial stop and target basis, standing trail or actual gap fills, causal gate timestamp. This does not independently recompute indicators or reconstruct tick order.')
    s.original.save(s.OUT/'execution_audit.json',evidence)
    print(evidence)


if __name__=='__main__':main()
