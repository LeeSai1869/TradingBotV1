"""Independent fill arithmetic and price-bar checks against frozen executions."""
import gzip
import json
import math
from pathlib import Path

OUT=Path(__file__).parent


def audit(symbol):
    with gzip.open(OUT/f'frozen_{symbol}_results.json.gz','rt') as f:r=json.load(f)
    with gzip.open(OUT/f'frozen_{symbol}_execution.json.gz','rt') as f:e=json.load(f)
    bars={(key.split(':')[0],row[0]):row for key,rows in e['blocks'].items() for row in rows}
    checks=0;targets=0;stops=0;trails=0;ordering_changes=0
    for case in r['case_traces']:
        policy=r['policies'][case['policy']];fee=policy['fee'];slip=policy['slip']
        a,b=case['traces']
        ordering_changes+=(a['status'],a.get('net_pct'))!=(b['status'],b.get('net_pct'))
        for t in case['traces']:
            if t['status']!='CLOSED':continue
            assert t['exit_time_upper']<=r['last'] and t['entry_time']==t['signal_known_time']
            expected=(t['exit_reference']*(1-slip)*(1-fee)/(t['entry_open']*(1+slip)*(1+fee))-1)*100
            assert math.isclose(expected,t['net_pct'],abs_tol=1e-9)
            if t['execution_tf']=='15m':continue
            raw=bars[t['execution_tf'],t['exit_bar_time']];o,h,l=raw[2:5];ref=t['exit_reference']
            at_open=t['exit_time_upper']==t['exit_bar_time']
            if t['reason']=='TAKE_PROFIT':
                assert h>=ref and math.isclose(t['net_pct'],1,abs_tol=1e-8);targets+=1
            elif t['reason']=='HARD_STOP':
                assert math.isclose(ref,o if at_open else t['hard_stop'],rel_tol=1e-10,abs_tol=1e-12)
                assert (o<=t['hard_stop']) if at_open else l<=ref<=h
                assert t['net_pct']<=-.5+1e-8;stops+=1
            elif t['reason']=='TRAILING_STOP':
                assert l-1e-10<=ref<=h+1e-10
                level=max(t['hard_stop'],t['highest']*(1-policy['trail']))
                assert ref<=level+1e-8
                assert at_open or math.isclose(ref,level,rel_tol=1e-9,abs_tol=1e-12) or math.isclose(ref,t['activation_price'],rel_tol=1e-9,abs_tol=1e-12)
                trails+=1
            checks+=1
    return dict(closed_execution_checks=checks,target_checks=targets,hard_stop_checks=stops,trailing_checks=trails,ordering_changed_cases=ordering_changes,mismatches=0)


if __name__=='__main__':
    result={symbol:audit(symbol) for symbol in ['BTCUSDT','SUIUSDT']}
    (OUT/'independent_execution_audit.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
