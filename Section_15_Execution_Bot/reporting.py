"""Print fills/errors/recovery promptly, and one quiet heartbeat per interval."""
import json


class Reporter:
    def __init__(self,interval=30):self.interval=interval;self.previous=None;self.last_print=None;self.bad=False

    def packet(self,results,now):
        signature=json.dumps([{k:v for k,v in row.items() if k!='paper_fills'} for row in results],sort_keys=True)
        changed=signature!=self.previous
        filled=any(row.get('paper_fills') for row in results)
        due=self.last_print is None or now-self.last_print>=self.interval
        if not (changed or filled or due):return None
        prior_bad=self.bad
        bad=any('error' in row or 'warning' in row for row in results)
        event='fill' if filled else 'error' if bad else 'recovered' if prior_bad else 'heartbeat'
        self.previous=signature;self.last_print=now;self.bad=bad
        return dict(event=event,results=results)
