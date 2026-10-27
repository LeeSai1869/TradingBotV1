"""Bounded, causal observations; heuristics describe evidence, not predictions.

One instance per synchronized feed session. Gaps reset rolling flow/CVD so a
reconnect cannot silently turn missing trades into zero activity.
"""
from collections import deque
import math


class Analytics:
    def __init__(self):
        self.rows=deque(maxlen=180)
        self.oi=deque(maxlen=180)
        self.cvd=0.
        self.segment_start=None

    def add(self, packet):
        now=packet['available_ms'];metrics=packet['metrics'];context=packet.get('context',{})
        previous=self.rows[-1] if self.rows else None
        continuous=packet.get('trade_coverage')=='continuous'
        if previous and (now<=previous['time'] or now-previous['time']>10000 or packet['window_start_ms']!=previous['time'] or not continuous):
            self.rows.clear();self.cvd=0.;self.segment_start=None
        buy=packet.get('aggressive_buy_usdt',0.);sell=packet.get('aggressive_sell_usdt',0.)
        # Partial startup/recovery windows never contribute to continuous CVD.
        if continuous:
            if self.segment_start is None:self.segment_start=packet['window_start_ms']
            self.cvd+=buy-sell
            self.rows.append(dict(time=now,start=packet['window_start_ms'],buy=buy,sell=sell,
                                  mid=metrics['mid'],spread=metrics['spread_bps'],
                                  imbalance=metrics.get('imbalance_10bps'),activity={k:v for k,v in metrics.items() if k.startswith('displayed_')}))
        output=dict(version=1,cvd_since_continuity_usdt=self.cvd if continuous else None,
                    continuity_start_ms=self.segment_start,heuristic=True)
        for seconds in (60,300):
            start=now-seconds*1000
            # Retain the whole straddling sample: trade totals cannot be
            # prorated honestly. Expose the actual observed window duration.
            rows=[r for r in self.rows if r['time']>start]
            covered=sum(max(0,min(10000,r['time']-r['start'])) for r in rows)
            complete=bool(rows) and covered>=seconds*1000-500 and rows[0]['start']<=start
            total_buy=sum(r['buy'] for r in rows);total_sell=sum(r['sell'] for r in rows)
            total=total_buy+total_sell;delta=total_buy-total_sell
            change=(rows[-1]['mid']/rows[0]['mid']-1)*10000 if complete else None
            imbalance=[r['imbalance'] for r in rows if r['imbalance'] is not None]
            # Require substantial directional flow plus limited net price response.
            pressure=delta/total if complete and total else None
            output[str(seconds)+'s']=dict(complete=complete,coverage=min(1,covered/(seconds*1000)),observed_window_ms=covered,
                aggressive_buy_usdt=total_buy if complete else None,
                aggressive_sell_usdt=total_sell if complete else None,
                delta_usdt=delta if complete else None,flow_imbalance=pressure,price_change_bps=change,
                mean_book_imbalance_10bps=sum(imbalance)/len(imbalance) if complete and len(imbalance)==len(rows) else None,
                buy_absorption_evidence=pressure is not None and pressure>=.6 and abs(change)<=2,
                sell_absorption_evidence=pressure is not None and pressure<=-.6 and abs(change)<=2)
        oi=context.get('open_interest');oi_time=context.get('open_interest_exchange_ms')
        if oi is not None and oi_time is not None and 0<=now-oi_time<=120000:
            if self.oi and oi_time<self.oi[-1][0]:self.oi.clear()
            if not self.oi or oi_time>self.oi[-1][0]:self.oi.append((oi_time,oi))
        while self.oi and self.oi[0][0]<now-900000:self.oi.popleft()
        baseline=next((value for stamp,value in reversed(self.oi) if stamp<=now-300000),None)
        output['open_interest_change_5m_pct']=(oi/baseline-1)*100 if oi is not None and oi_time is not None and 0<=now-oi_time<=120000 and baseline else None
        mark=context.get('mark_price');index=context.get('index_price')
        output['mark_index_basis_bps']=(mark/index-1)*10000 if mark and index else None
        bands=packet.get('bands',[])
        for side in ('bid','ask'):
            selected=[b for b in bands if b['side']==side];total=sum(b['notional_usdt'] for b in selected)
            output[side+'_persistent_30s_share']=sum(b['notional_usdt'] for b in selected if b.get('sampled_presence_ms',0)>=30000)/total if total else None
        # Realized variability is measured from continuous observations only.
        recent=[r for r in self.rows if r['start']>=now-60000]
        returns=[(b['mid']/a['mid']-1)*10000 for a,b in zip(recent,recent[1:])]
        output['realized_volatility_60s_bps']=math.sqrt(sum(r*r for r in returns)) if output['60s']['complete'] else None
        if previous and now>previous['time'] and now-previous['time']<=10000:
            for side in ('bid','ask'):
                for kind in ('added','removed'):
                    key=f'displayed_{side}_{kind}_usdt_since_sync'
                    current=metrics.get(key);old=previous.get('activity',{}).get(key)
                    output[f'displayed_{side}_{kind}_usdt_window']=current-old if current is not None and old is not None and current>=old else None
        path=sum(abs(r) for r in returns)
        net=abs((recent[-1]['mid']/recent[0]['mid']-1)*10000) if len(recent)>1 else 0.
        output['directional_efficiency_60s']=min(1,net/path) if output['60s']['complete'] and path else None
        efficiency=output['directional_efficiency_60s']
        output['microstructure_regime']=('warming_up' if not output['60s']['complete'] else
            'quiet' if not path else 'directional' if efficiency>=.7 else 'two_way')
        packet['analytics']=output
        packet['health']=dict(book_age_ms=now-packet['book_received_ms'],exchange_age_ms=now-packet['exchange_ms'],
            trade_coverage=packet.get('trade_coverage'),
            open_interest_fresh=oi is not None and oi_time is not None and 0<=now-oi_time<=120000,
            mark_context_fresh=mark is not None and index is not None,
            requested_radius_bps=packet.get('radius_bps'),observed_coverage=packet.get('coverage',{}))
        return packet
