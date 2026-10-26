"""Binance USD-M local book: snapshot bridge U <= lastUpdateId <= u, then pu.

Quantities are absolute replacements; zero deletes. Snapshot depth is finite:
coverage is limited to its original outer prices, never advertised as full depth.
"""
from decimal import Decimal, InvalidOperation
import math

class Gap(ValueError):pass


def levels(rows):
    result={}
    for p,q in rows:
        try:p,q=Decimal(str(p)),Decimal(str(q))
        except InvalidOperation as error:raise Gap('Invalid depth number') from error
        if not p.is_finite() or not q.is_finite() or p<=0 or q<0:raise Gap('Invalid depth level')
        result[p]=q
    return result


class Book:
    def __init__(self,symbol):
        self.symbol=symbol;self.ready=False;self.last=None;self.bridged=False
        self.bids={};self.asks={};self.exchange_ms=None;self.received_ms=None
    def invalidate(self):self.ready=False
    def snapshot(self,payload):
        self.ready=False
        bids={p:q for p,q in levels(payload['bids']).items() if q};asks={p:q for p,q in levels(payload['asks']).items() if q}
        if not bids or not asks or max(bids)>=min(asks):raise Gap('Empty/crossed snapshot')
        self.bids,self.asks=bids,asks;self.last=int(payload['lastUpdateId']);self.bridged=False
        self.floor=min(bids);self.ceiling=max(asks)
        self.activity={f'displayed_{side}_{kind}_usdt_since_sync':0. for side in ('bid','ask') for kind in ('added','removed')}
    def apply(self,event,received_ms):
        try:return self._apply(event,received_ms)
        except (ValueError,KeyError,TypeError) as error:
            self.ready=False;self.last=None
            raise Gap(str(error)) from error

    def _apply(self,event,received_ms):
        if event.get('s')!=self.symbol:raise Gap('Wrong book symbol')
        first,last,previous=int(event['U']),int(event['u']),int(event['pu'])
        if first>last:raise Gap('Inverted update sequence')
        if self.last is None:raise Gap('Snapshot required')
        if last<self.last or self.bridged and last==self.last:return False
        if not self.bridged:
            if not first<=self.last<=last:raise Gap('Snapshot bridge missing')
        elif previous!=self.last:
            self.ready=False;raise Gap('Depth sequence gap')
        bids,asks=levels(event['b']),levels(event['a'])
        # Keep only the snapshot-covered range. A few outer delta prices do not
        # establish knowledge of every intervening level outside that range.
        for name,side,updates in (('bid',self.bids,bids),('ask',self.asks,asks)):
            for p,q in updates.items():
                if self.floor<=p<=self.ceiling:
                    delta=(q-side.get(p,Decimal(0)))*p
                    self.activity[f'displayed_{name}_{"added" if delta>0 else "removed"}_usdt_since_sync']+=abs(float(delta))
                    if q:side[p]=q
                    else:side.pop(p,None)
        if not self.bids or not self.asks or max(self.bids)>=min(self.asks):
            self.ready=False;raise Gap('Empty/crossed updated book')
        if max(self.bids)<=self.floor or min(self.asks)>=self.ceiling:
            self.ready=False;raise Gap('Snapshot coverage exhausted')
        self.last=last;self.bridged=True;self.ready=True
        self.exchange_ms=int(event['E']);self.transaction_ms=int(event.get('T',event['E']));self.received_ms=int(received_ms)
        return True

    def features(self,now_ms,*,band_bps=10,radius_bps=100,stale_ms=10000):
        if not self.ready or now_ms-self.received_ms>stale_ms or self.received_ms>now_ms:raise Gap('Book is not fresh and synchronized')
        if abs(now_ms-self.exchange_ms)>stale_ms:raise Gap('Delayed exchange book or local clock skew')
        bids=sorted(self.bids.items(),reverse=True);asks=sorted(self.asks.items())
        bid,ask=bids[0][0],asks[0][0];mid=(bid+ask)/2
        coverage={'bid_bps':float((mid-self.floor)/mid*10000),'ask_bps':float((self.ceiling-mid)/mid*10000),'snapshot_limit':1000}
        metrics={**self.activity,'transport_delay_ms':self.received_ms-self.exchange_ms,'mid':float(mid),'best_bid':float(bid),'best_ask':float(ask),'spread_bps':float((ask-bid)/mid*10000)}
        for distance in (5,10,25,50,100):
            for side,rows in (('bid',bids),('ask',asks)):
                metrics[f'{side}_depth_{distance}bps_usdt']=(sum(float(p*q) for p,q in rows if abs(p-mid)/mid*10000<=distance)
                    if coverage[side+'_bps']>=distance else None)
            buy,sell=metrics[f'bid_depth_{distance}bps_usdt'],metrics[f'ask_depth_{distance}bps_usdt']
            metrics[f'imbalance_{distance}bps']=((buy-sell)/(buy+sell) if buy is not None and sell is not None and buy+sell else None)
        for notional in (1000,10000,100000):
            for side,rows in (('buy',asks),('sell',bids)):
                remaining=Decimal(notional);base=Decimal(0)
                for p,q in rows:
                    take=min(remaining,p*q);base+=take/p;remaining-=take
                    if remaining<=0:break
                vwap=Decimal(notional)/base if base and remaining<=0 else None
                metrics[f'{side}_slippage_{notional}_usdt_bps']=(float((vwap-mid)/mid*10000*(1 if side=='buy' else -1)) if vwap else None)
        # Stable logarithmic price grid, not bins that shift with every new mid.
        step=math.log1p(band_bps/10000);bands={}
        for side,rows in (('bid',bids),('ask',asks)):
            for p,q in rows:
                if abs(p-mid)/mid*10000>radius_bps:continue
                index=math.floor(math.log(float(p))/step);key=(side,index)
                item=bands.setdefault(key,dict(side=side,low=math.exp(index*step),high=math.exp((index+1)*step),notional_usdt=0.))
                item['notional_usdt']+=float(p*q)
        return dict(venue='binance',market='usdt_perpetual',symbol=self.symbol,quote='USDT',observed=True,
                    exchange_ms=self.exchange_ms,transaction_ms=self.transaction_ms,available_ms=now_ms,book_received_ms=self.received_ms,sequence=self.last,
                    band_bps=band_bps,radius_bps=radius_bps,coverage=coverage,metrics=metrics,
                    bands=sorted(bands.values(),key=lambda x:(x['low'],x['side'])))
