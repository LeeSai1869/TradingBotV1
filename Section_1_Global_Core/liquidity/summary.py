"""Closed minute summaries with measured coverage, not invented missing values."""
class Minutes:
    def __init__(self,symbol):self.symbol=symbol;self.open=None;self.rows=[]
    def add(self,sample):
        minute=sample.get('sampled_ms',sample['available_ms'])//60000*60000;closed=None
        if self.open is not None and minute<self.open:self.open=None;self.rows=[]
        if self.open is not None and minute!=self.open:
            metrics={}
            keys={k for r in self.rows for k in r['metrics']}
            for key in keys:
                values=[r['metrics'][key] for r in self.rows if r['metrics'].get(key) is not None]
                metrics[key]=sum(values)/len(values) if values else None
            # Five-second snapshots cover at most five seconds, never bridge a
            # reconnect/sleep gap. Coverage is essential for interpreting means.
            covered=sum(min(5000,max(0,min(self.open+60000,r.get('sampled_ms',r['available_ms']))-max(self.open,r.get('book_window_start_ms',r['available_ms'])))) for r in self.rows)
            flow_rows=[r for r in self.rows if r.get('window_start_ms',-1)>=self.open]
            closed=dict(venue='binance',market='usdt_perpetual',symbol=self.symbol,open_ms=self.open,
                        close_ms=self.open+60000-1,available_ms=sample['available_ms'],coverage=min(1,covered/60000),
                        samples=len(self.rows),metrics_mean=metrics,analytics_last=self.rows[-1].get('analytics',{}),health_last=self.rows[-1].get('health',{}),context_last=self.rows[-1].get('context',{}),
                        reported_long_liquidations_usdt=sum(r.get('reported_long_liquidations_usdt',0) for r in flow_rows),
                        reported_short_liquidations_usdt=sum(r.get('reported_short_liquidations_usdt',0) for r in flow_rows),
                        liquidation_coverage='sampled exchange stream, within sampled windows only',
                        continuous_trade_samples=sum(r.get('trade_coverage')=='continuous' for r in self.rows),
                        sampled_aggressive_buy_usdt=sum(r.get('aggressive_buy_usdt',0) for r in flow_rows),
                        sampled_aggressive_sell_usdt=sum(r.get('aggressive_sell_usdt',0) for r in flow_rows),trade_coverage='sampled windows; see sample-level continuity')
            self.rows=[]
        self.open=minute;self.rows.append(sample)
        return closed
