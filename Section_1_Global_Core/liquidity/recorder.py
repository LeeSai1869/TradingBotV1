"""Independent public USD-M feed. Snapshot/recovery HTTP never blocks WS reads."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import json
import math
import queue
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from .book import Book,Gap
from . import store
from .archive import Archive
from .summary import Minutes

REST='https://fapi.binance.com'
WS='wss://fstream.binance.com/stream?streams='

class Backpressure(RuntimeError):pass

def number(value,*,signed=False):
    value=float(value)
    if not math.isfinite(value) or not signed and value<0:raise Gap('Invalid exchange numeric field')
    return value

def reject_constant(value):raise Gap('Non-finite exchange JSON: '+value)

class RESTClient:
    def __init__(self):self.lock=threading.Lock();self.next=0
    def get(self,path,**params):
        # At most one new request/second across snapshots, OI and discovery.
        # A 1000-level snapshot costs more than a single ordinary REST request.
        with self.lock:
            delay=max(0,self.next-time.monotonic())
            if delay>5:raise Gap('Exchange REST cooldown is active')
            if delay:time.sleep(delay)
            self.next=time.monotonic()+1
        url=REST+path+('?' +urllib.parse.urlencode(params) if params else '')
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'TradingBotV1-liquidity/1'}),timeout=8) as response:return json.load(response,parse_constant=reject_constant)
        except urllib.error.HTTPError as error:
            try:
                if error.code in (418,429):
                    try:pause=max(60,min(3600,float((error.headers or {}).get('Retry-After',60))))
                    except ValueError:pause=60
                    with self.lock:self.next=max(self.next,time.monotonic()+pause)
            finally:error.close()
            raise


class Writer(threading.Thread):
    def __init__(self):
        super().__init__(name='liquidity-writer',daemon=True)
        self.raw_queue=queue.Queue(20000);self.control=queue.Queue(1000)
        self.stopping=threading.Event();self.failed=threading.Event();self.error=None
    def raw(self,symbol,payload,received_ms,kind='stream'):
        try:self.raw_queue.put_nowait((symbol,dict(venue='binance',market='usdt_perpetual',symbol=symbol,received_ms=received_ms,kind=kind,payload=payload)))
        except queue.Full as error:raise Backpressure('Raw archive queue overflow; resynchronizing') from error
    def status(self,symbol,state,reason=''):
        self.control.put(('status',(symbol,state,reason,int(time.time()*1000))),timeout=2)
    def sample(self,payload):self.control.put(('sample',payload),timeout=2)
    def run(self):
        conn=None;archive=Archive(store.ROOT/'raw');minutes={};last_flush=0;last_prune=0
        try:
            conn=store.open_writer()
            while not self.stopping.is_set() or not self.control.empty() or not self.raw_queue.empty():
                control_changed=False
                for _ in range(100):
                    try:kind,payload=self.control.get_nowait()
                    except queue.Empty:break
                    control_changed=True
                    if kind=='status':store.set_status(conn,*payload)
                    else:
                        stored=store.write_sample(conn,payload)
                        closed=minutes.setdefault(payload['symbol'],Minutes(payload['symbol'])).add(stored)
                        if closed:store.write_candle(conn,closed)
                if control_changed:conn.commit()
                for _ in range(1000):
                    try:symbol,record=self.raw_queue.get(timeout=.02)
                    except queue.Empty:break
                    archive.append(symbol,record)
                now=time.time()
                if now-last_flush>=.5:conn.commit();archive.flush();last_flush=now
                if now-last_prune>=60:
                    store.prune(conn,int(now*1000));archive.prune(int(now*1000));last_prune=now
            conn.commit()
        except BaseException as error:
            self.error=str(error);self.failed.set()
            import traceback;traceback.print_exc()
        finally:
            try:archive.close()
            except OSError as error:
                self.error=self.error or str(error);self.failed.set()
                print(f'[liquidity] archive close failed: {error}',flush=True)
            finally:
                if conn:conn.close()


class Worker(threading.Thread):
    def __init__(self,symbol,writer,rest,snapshots,context,*,connect=None):
        super().__init__(name='liquidity-'+symbol,daemon=True)
        self.symbol=symbol;self.writer=writer;self.rest=rest;self.snapshots=snapshots;self.context=context;self.connect=connect
        self.stopping=threading.Event();self.socket=None
    def stop(self):
        self.stopping.set()
        if self.socket:
            try:self.socket.close()
            except Exception:pass
    def run(self):
        delay=1
        while not self.stopping.is_set() and not self.writer.failed.is_set():
            try:self.session();delay=1
            except Exception as error:
                if not self.stopping.is_set():
                    print(f'[liquidity] {self.symbol}: {error}',flush=True)
                    try:self.writer.status(self.symbol,'resynchronizing',str(error))
                    except queue.Full:pass
            finally:
                if self.socket:
                    try:self.socket.close()
                    except Exception:pass
                    self.socket=None
            if self.stopping.wait(delay):break
            delay=min(30,delay*2)
        try:self.writer.status(self.symbol,'stopped','Recorder stopped or symbol paused')
        except queue.Full:pass

    def session(self):
        self.pending_snapshot=self.pending_context=None
        try:self._session()
        finally:
            for pending in (self.pending_snapshot,self.pending_context):
                if pending:pending.cancel()

    def _session(self):
        import websocket
        symbol=self.symbol.lower()
        streams=[symbol+'@depth@100ms',symbol+'@aggTrade',symbol+'@forceOrder',symbol+'@markPrice@1s']
        self.writer.status(self.symbol,'synchronizing','Waiting for depth snapshot and sequence bridge')
        self.socket=(self.connect or websocket.create_connection)(WS+'/'.join(streams),timeout=8,enable_multithread=True)
        self.socket.settimeout(.5)
        snapshot=self.pending_snapshot=self.snapshots.submit(self.rest.get,'/fapi/v1/depth',symbol=self.symbol,limit=1000)
        book=Book(self.symbol);buffer=deque();loaded=False
        last_publish=0;last_book=0;began=time.monotonic();context_future=None;next_context=0
        info={};trade_buy=trade_sell=long_liq=short_liq=0.;last_trade=None;trade_complete=False
        band_presence={};previous_depth={}
        liquidations=deque(maxlen=100);last_window=int(time.time()*1000)
        while not self.stopping.is_set() and not self.writer.failed.is_set():
            now=int(time.time()*1000)
            if not loaded and snapshot.done():
                payload=snapshot.result();book.snapshot(payload);self.writer.raw(self.symbol,payload,now,'snapshot')
                loaded=True
                for event,received in buffer:book.apply(event,received)
                buffer.clear()
            if context_future and context_future.done():
                try:
                    oi=context_future.result();info.update(open_interest=number(oi['openInterest']),open_interest_received_ms=now,open_interest_exchange_ms=int(oi['time']))
                    info.pop('open_interest_error',None)
                    self.writer.raw(self.symbol,oi,now,'open_interest')
                except (OSError,ValueError,KeyError) as error:info.update(open_interest=None,open_interest_error=str(error))
                context_future=None
            if loaded and now>=next_context and context_future is None:
                context_future=self.pending_context=self.context.submit(self.rest.get,'/fapi/v1/openInterest',symbol=self.symbol);next_context=now+60000
            try:
                raw=self.socket.recv()
                if not raw:raise Gap('WebSocket closed')
                received=int(time.time()*1000);message=json.loads(raw,parse_constant=reject_constant);event=message.get('data',message)
                if event.get('s',event.get('o',{}).get('s'))!=self.symbol:raise Gap('Unexpected stream symbol')
                self.writer.raw(self.symbol,event,received)
                kind=event.get('e')
                if kind=='depthUpdate':
                    if loaded:book.apply(event,received)
                    else:
                        if len(buffer)>=10000:raise Gap('Snapshot buffer overflow')
                        buffer.append((event,received))
                    last_book=received
                elif kind=='aggTrade':
                    identity=int(event['a'])
                    if last_trade is None or identity>last_trade:
                        if last_trade is not None and identity!=last_trade+1:trade_complete=False
                        value=number(event['p'])*number(event['q'])
                        if event['m']:trade_sell+=value
                        else:trade_buy+=value
                        last_trade=identity
                elif kind=='forceOrder':
                    order=event['o'];identity=json.dumps(order,sort_keys=True)
                    if identity not in liquidations:
                        liquidations.append(identity)
                        value=number(order['ap'])*number(order['l'])
                        if order['S']=='SELL':long_liq+=value
                        else:short_liq+=value
                elif kind=='markPriceUpdate':
                    info.update(mark_price=number(event['p']),index_price=number(event['i']),funding_rate=number(event['r'],signed=True),next_funding_ms=int(event['T']),mark_received_ms=received)
            except websocket.WebSocketTimeoutException:pass
            now=int(time.time()*1000)
            if loaded and book.ready and now-last_publish>=5000:
                packet=book.features(now)
                current_presence={}
                for band in packet['bands']:
                    key=(band['side'],band['low']);since=band_presence.get(key,now)
                    band['sampled_presence_ms']=now-since;current_presence[key]=since
                band_presence=current_presence
                for side in ('bid','ask'):
                    key=side+'_depth_10bps_usdt';current=packet['metrics'][key];previous=previous_depth.get(key)
                    packet['metrics'][side+'_depth_10bps_change_usdt']=current-previous if current is not None and previous is not None else None
                    previous_depth[key]=current
                if info.get('open_interest_received_ms',0)<now-120000:info['open_interest']=None
                if info.get('mark_received_ms',0)<now-10000:
                    for key in ('mark_price','index_price','funding_rate'):info[key]=None
                packet.update(book_window_start_ms=last_publish or now,context=dict(info),aggressive_buy_usdt=trade_buy,aggressive_sell_usdt=trade_sell,
                    trade_coverage='continuous' if trade_complete else 'partial',window_start_ms=last_window or now,
                    reported_long_liquidations_usdt=long_liq,reported_short_liquidations_usdt=short_liq,
                    liquidation_coverage='sampled exchange forceOrder stream; not all liquidations')
                json.dumps(packet,allow_nan=False) # Quarantine malformed data per symbol, not in the shared writer.
                self.writer.sample(packet);last_publish=now;last_window=now
                trade_buy=trade_sell=long_liq=short_liq=0.;trade_complete=last_trade is not None
            if now-last_book>10000 and time.monotonic()-began>10:raise Gap('No fresh depth updates')
            if not loaded and time.monotonic()-began>120:raise Gap('Snapshot initialization timed out')
        snapshot.cancel()
        if context_future:context_future.cancel()
