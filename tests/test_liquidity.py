from contextlib import ExitStack
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Section_1_Global_Core.liquidity.book import Book,Gap
from Section_1_Global_Core.liquidity import store
from Section_1_Global_Core.liquidity.archive import Archive
from Section_1_Global_Core.liquidity.summary import Minutes
from Section_1_Global_Core.liquidity.runner import instruments


def snapshot():return dict(lastUpdateId=10,bids=[['100','2'],['99','3'],['95','1']],asks=[['101','4'],['102','5'],['106','1']])
def event(first=10,last=11,previous=9,**changes):return dict(e='depthUpdate',s='BTCUSDT',E=1000,T=1000,U=first,u=last,pu=previous,b=[],a=[],**changes)
def ready():
    b=Book('BTCUSDT');b.snapshot(snapshot());b.apply(event(),1000);return b

class BookTests(unittest.TestCase):
    def test_bridge_absolute_replacements_zero_removal_and_duplicate(self):
        b=Book('BTCUSDT');b.snapshot(snapshot());self.assertFalse(b.ready)
        self.assertFalse(b.apply(event(8,9,7),999));self.assertTrue(b.apply(event(),1000))
        update=event(12,13,11);update.update(b=[['100','7'],['99','0']])
        b.apply(update,1100)
        self.assertEqual(float(b.bids[__import__('decimal').Decimal(100)]),7)
        self.assertNotIn(__import__('decimal').Decimal(99),b.bids)
        self.assertFalse(b.apply(update,1200));self.assertEqual(b.received_ms,1100)

    def test_gap_crossed_empty_and_missing_bridge_are_never_valid(self):
        b=ready()
        with self.assertRaises(Gap):b.apply(event(20,21,19),1100)
        self.assertFalse(b.ready)
        b=Book('BTCUSDT');b.snapshot(snapshot())
        with self.assertRaises(Gap):b.apply(event(12,13,11),1000)
        for rows in ([['100','-1']],[['NaN','1']],[['0','2']]):
            bad=snapshot();bad['bids']=rows
            with self.assertRaises(Gap):Book('BTCUSDT').snapshot(bad)
        b=ready();e=event(12,12,11);e['b']=[['102','1']]
        with self.assertRaises(Gap):b.apply(e,1100)
        self.assertFalse(b.ready)

    def test_usdt_bands_depth_imbalance_slippage_and_finite_coverage(self):
        b=ready();sample=b.features(1000,band_bps=10,radius_bps=100)
        m=sample['metrics']
        self.assertEqual(m['mid'],100.5)
        self.assertAlmostEqual(m['bid_depth_50bps_usdt'],200)
        self.assertAlmostEqual(m['ask_depth_50bps_usdt'],404)
        self.assertAlmostEqual(m['imbalance_50bps'],(200-404)/(200+404))
        self.assertIsNone(m['buy_slippage_10000_usdt_bps'])
        self.assertIsNotNone(m['buy_slippage_1000_usdt_bps'])
        self.assertGreater(m['buy_slippage_1000_usdt_bps'],0)
        self.assertEqual(sum(r['notional_usdt'] for r in sample['bands'] if r['side']=='bid'),200)
        for r in sample['bands']:self.assertLess(r['low'],r['high'])
        with self.assertRaises(Gap):b.features(11001)
        with self.assertRaises(Gap):b.features(999)
        thin=snapshot();thin['bids']=[['100','2'],['99.9','1']];thin['asks']=[['101','4'],['101.1','1']]
        b=Book('BTCUSDT');b.snapshot(thin);b.apply(event(),1000)
        self.assertIsNone(b.features(1000)['metrics']['bid_depth_100bps_usdt'])

    def test_receiving_old_buffered_exchange_data_does_not_make_it_live(self):
        b=Book('BTCUSDT');b.snapshot(snapshot());b.apply(event(),100000)
        with self.assertRaisesRegex(Gap,'Delayed exchange'):b.features(100000)

    def test_instrument_discovery_never_mix_spot_dated_or_coin_margined(self):
        rows=[dict(symbol='BTCUSDT',contractType='PERPETUAL',quoteAsset='USDT',status='TRADING')]
        for key,value in [('contractType','CURRENT_QUARTER'),('quoteAsset','USD'),('status','SETTLING')]:rows.append({**rows[0],key:value,'symbol':'ETHUSDT'})
        self.assertEqual(instruments(dict(symbols=rows)),{'BTCUSDT'})

class LiquidityMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'liq.db';self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(store,'DB_PATH',self.path))
        self.conn=store.open_writer();self.addCleanup(self.conn.close)
    def save(self,time=1000):
        sample=ready().features(1000);sample['window_start_ms']=1000;sample['book_window_start_ms']=1000
        with self.conn:return store.write_sample(self.conn,sample,time)

    def test_fresh_stale_gap_and_asof_without_future_fill(self):
        self.save(1200)
        self.assertIsNone(store.features_at('BTCUSDT',1199))
        self.assertEqual(store.features_at('BTCUSDT',1200)['market'],'usdt_perpetual')
        self.assertEqual(store.snapshot('BTCUSDT',now_ms=1200)['status'],'live')
        self.assertIsNone(store.snapshot('BTCUSDT',now_ms=11001)['latest'])
        with self.conn:store.set_status(self.conn,'BTCUSDT','resynchronizing','sequence gap',1500)
        self.assertIsNone(store.features_at('BTCUSDT',1600))
        self.assertIsNotNone(store.features_at('BTCUSDT',1400))
        self.assertIsNone(store.snapshot('BTCUSDT',now_ms=1600)['latest'])
        self.assertEqual(len(store.snapshot('BTCUSDT',now_ms=1600)['history']),1)

    def test_gap_before_a_delayed_write_still_invalidates_that_sample(self):
        self.save(2000)
        with self.conn:store.set_status(self.conn,'BTCUSDT','resynchronizing','sequence gap',1500)
        self.assertIsNone(store.features_at('BTCUSDT',2200))

    def test_read_only_missing_store_does_not_create_and_closed_summary_availability(self):
        with patch.object(store,'DB_PATH',Path(self.tmp.name)/'missing.db'):
            self.assertEqual(store.snapshot('BTCUSDT')['status'],'not recording')
            self.assertFalse(store.DB_PATH.exists())
        minutes=Minutes('BTCUSDT');s=self.save()
        self.assertIsNone(minutes.add(s))
        second={**s,'sampled_ms':61000,'available_ms':62000}
        closed=minutes.add(second)
        self.assertEqual(closed['open_ms'],0);self.assertEqual(closed['coverage'],0)
        with self.conn:store.write_candle(self.conn,closed)
        self.assertIsNone(store.candle_features_at('BTCUSDT',0,61999))
        self.assertEqual(store.candle_features_at('BTCUSDT',0,62000)['samples'],1)

    def test_owned_archive_is_readable_and_bounded(self):
        root=Path(self.tmp.name)/'archive';archive=Archive(root,budget=0)
        for symbol in ('BTCUSDT','ETHUSDT'):archive.append(symbol,dict(received_ms=1000,payload={'u':11}))
        archive.close();files=list(root.rglob('*.gz'));self.assertEqual(len(files),2)
        for path in files:
            with gzip.open(path,'rt') as f:self.assertEqual(json.loads(f.readline())['payload']['u'],11)
        unrelated=root/'unrelated.txt';unrelated.write_text('keep')
        archive.prune(1000000);self.assertFalse(list(root.rglob('*.gz')));self.assertTrue(unrelated.exists())

    def test_archive_rotates_open_chunks_and_bounds_handles(self):
        archive=Archive(Path(self.tmp.name)/'rotating',chunk_bytes=1,max_handles=2)
        for i in range(257):archive.append('BTCUSDT',dict(received_ms=1000,payload={'u':i}))
        self.assertGreaterEqual(len(list(archive.root.rglob('*.gz'))),2)
        for symbol in ('ETHUSDT','BNBUSDT','SUIUSDT'):archive.append(symbol,dict(received_ms=1000,payload={}))
        self.assertLessEqual(len(archive.handles),2);archive.close()


class RecorderTests(unittest.TestCase):
    def test_stream_records_perpetual_trade_direction_liquidations_and_context_without_network(self):
        from concurrent.futures import Future
        import threading
        from Section_1_Global_Core.liquidity import recorder
        clock=[1000.]
        messages=[event(),dict(e='aggTrade',s='BTCUSDT',a=1,p='101',q='2',m=False),
                  dict(e='aggTrade',s='BTCUSDT',a=2,p='100',q='3',m=True),
                  dict(e='forceOrder',E=1,o=dict(s='BTCUSDT',S='SELL',ap='100',l='1',T=1)),
                  dict(e='markPriceUpdate',s='BTCUSDT',p='101',i='100.5',r='.0001',T=2000000),event(12,12,11),event(20,21,19)]
        class Socket:
            def settimeout(self,*_):pass
            def recv(self):
                clock[0]+=1;message=messages.pop(0);message['E']=int(clock[0]*1000)
                if message['e']=='depthUpdate':message['T']=message['E']
                return json.dumps(message)
            def close(self):pass
        class REST:
            def get(self,path,**params):return snapshot() if path.endswith('depth') else dict(openInterest='12',time=1000000)
        class Pool:
            def submit(self,fn,*args,**kwargs):
                future=Future();future.set_result(fn(*args,**kwargs));return future
        class Writer:
            def __init__(self):self.failed=threading.Event();self.samples=[];self.records=[]
            def raw(self,*args):self.records.append(args)
            def sample(self,p):self.samples.append(p)
            def status(self,*_):pass
        writer=Writer();worker=recorder.Worker('BTCUSDT',writer,REST(),Pool(),Pool(),connect=lambda *_args,**_kwargs:Socket())
        with patch.object(recorder.time,'time',side_effect=lambda:clock[0]):
            with self.assertRaisesRegex(Gap,'sequence gap'):worker.session()
        last=writer.samples[-1]
        self.assertEqual(last['market'],'usdt_perpetual')
        self.assertEqual(last['aggressive_buy_usdt'],202)
        self.assertEqual(last['aggressive_sell_usdt'],300)
        self.assertEqual(last['reported_long_liquidations_usdt'],100)
        self.assertEqual(last['context']['open_interest'],12)
        self.assertEqual(last['context']['funding_rate'],.0001)
        self.assertIn('not all liquidations',last['liquidation_coverage'])
        self.assertEqual(len(writer.samples),2) # No feature published after the sequence gap.
        self.assertTrue(any(args[3:] == ('snapshot',) for args in writer.records))

    def test_archive_backpressure_is_explicit_and_storage_failure_stops_writer(self):
        import queue
        from Section_1_Global_Core.liquidity import recorder
        writer=recorder.Writer();writer.raw_queue=queue.Queue(1)
        writer.raw('BTCUSDT',{},1000)
        with self.assertRaises(recorder.Backpressure):writer.raw('BTCUSDT',{},1001)
        with patch.object(recorder.store,'open_writer',side_effect=OSError('disk full')),patch('traceback.print_exc'):
            writer.run()
        self.assertTrue(writer.failed.is_set());self.assertIn('disk full',writer.error)

    def test_real_writer_drains_to_independent_memory_and_raw_archive(self):
        import time
        from Section_1_Global_Core.liquidity import recorder
        with tempfile.TemporaryDirectory() as directory,patch.object(store,'ROOT',Path(directory)),patch.object(store,'DB_PATH',Path(directory)/'liquidity.db'):
            writer=recorder.Writer();writer.start()
            try:
                stamp=int(time.time()*1000);b=Book('BTCUSDT');b.snapshot(snapshot())
                update=event();update.update(E=stamp,T=stamp);b.apply(update,stamp)
                writer.raw('BTCUSDT',update,stamp);writer.sample(b.features(stamp))
                writer.stopping.set();writer.join(timeout=3)
                self.assertFalse(writer.is_alive());self.assertFalse(writer.failed.is_set(),writer.error)
                self.assertEqual(store.snapshot('BTCUSDT')['status'],'live')
                paths=list(Path(directory).rglob('*.jsonl.gz'));self.assertEqual(len(paths),1)
                with gzip.open(paths[0],'rt') as stream:self.assertEqual(json.loads(stream.readline())['payload']['u'],11)
            finally:
                writer.stopping.set();writer.join(timeout=3)

    def test_cleanup_attempts_every_archive_handle_and_closes_database_on_flush_failure(self):
        from unittest.mock import Mock
        import sqlite3
        from Section_1_Global_Core.liquidity import recorder
        with tempfile.TemporaryDirectory() as directory:
            archive=Archive(Path(directory));first=Mock();second=Mock();first.close.side_effect=OSError('disk full')
            archive.handles['first']=first;archive.handles['second']=second
            with self.assertRaises(OSError):archive.close()
            second.close.assert_called_once();self.assertEqual(len(archive.handles),0)
            conn=store.open_writer(Path(directory)/'test.db');writer=recorder.Writer();writer.stopping.set()
            with patch.object(recorder.store,'open_writer',return_value=conn),patch.object(recorder.Archive,'close',side_effect=OSError('disk full')),patch('builtins.print'):
                writer.run()
            self.assertTrue(writer.failed.is_set())
            with self.assertRaises(sqlite3.ProgrammingError):conn.execute('SELECT 1')

    def test_exchange_rate_limit_enters_global_cooldown_without_hammering(self):
        import urllib.error
        from Section_1_Global_Core.liquidity import recorder
        rest=recorder.RESTClient()
        error=urllib.error.HTTPError('https://fapi.binance.com',429,'rate limited',{'Retry-After':'120'},None)
        with patch.object(recorder.time,'monotonic',return_value=100),patch.object(recorder.urllib.request,'urlopen',side_effect=error) as request:
            with self.assertRaises(urllib.error.HTTPError):rest.get('/fapi/v1/depth',symbol='BTCUSDT')
            with self.assertRaisesRegex(Gap,'cooldown'):rest.get('/fapi/v1/depth',symbol='ETHUSDT')
            self.assertEqual(request.call_count,1);self.assertEqual(rest.next,220);self.assertTrue(error.closed)


class LiquidityStartupTests(unittest.TestCase):
    def test_login_service_is_independent_and_uses_this_checkout(self):
        import restart_liquidity
        config=restart_liquidity.configuration(Path('/python314'),Path('/logs'))
        self.assertTrue(config['KeepAlive']);self.assertTrue(config['RunAtLoad'])
        self.assertEqual(config['WorkingDirectory'],str(restart_liquidity.ROOT))
        self.assertEqual(config['ProgramArguments'][-1],'Section_1_Global_Core.liquidity.runner')
        self.assertEqual(config['StandardErrorPath'],'/logs/liquidity-error.log')
