"""Nonblocking forming-candle snapshots; no market data is written to disk."""
import threading
import unittest
from Section_11_UI_UX.server.live_candle import FormingCandleCache


def raw(close=11):
    return dict(time=60,open_time=60000,close_time=119999,open=10,high=12,low=9,close=close,volume=5)


class LiveCandleTests(unittest.TestCase):
    def test_price_available_while_provisional_indicators_are_blocked(self):
        from unittest.mock import patch
        entered=threading.Event();release=threading.Event()
        def calculate(*args,**kwargs):
            entered.set();release.wait(3);return {'rsi':55}
        cache=FormingCandleCache(lambda *_:raw(),poll_seconds=10000,wall_clock=lambda:100)
        try:
            with patch('Section_11_UI_UX.server.live_features.calculate',side_effect=calculate):
                cache.snapshot('BTCUSDT','1m')
                self.assertTrue(entered.wait(1))
                result=cache.snapshot('BTCUSDT','1m')
                self.assertEqual(result['status'],'live')
                self.assertEqual(result['bar']['client']['close'],11)
                self.assertIsNone(result['bar']['features'])
                self.assertEqual(result['bar']['features_status'],'calculating')
                release.set();cache.close()
            self.assertEqual(cache.snapshot('BTCUSDT','1m')['bar']['features'],{'rsi':55})
        finally:release.set();cache.close()

    def test_slow_features_never_stop_later_price_ticks_or_overwrite_fresh_price(self):
        import time
        from unittest.mock import patch
        entered=threading.Event();release=threading.Event();fetched=threading.Event();calls=[]
        def fetch(*args):
            calls.append(1)
            if len(calls)>1:fetched.set()
            return raw(10+len(calls))
        def calculate(*args,**kwargs):entered.set();release.wait(3);return {'rsi':99}
        cache=FormingCandleCache(fetch,poll_seconds=0,wall_clock=lambda:100)
        try:
            with patch('Section_11_UI_UX.server.live_features.calculate',side_effect=calculate):
                cache.snapshot('BTCUSDT','5m');self.assertTrue(entered.wait(1))
                deadline=time.monotonic()+1
                while cache._entries['BTCUSDT','5m']['pending'] and time.monotonic()<deadline:time.sleep(.001)
                cache.snapshot('BTCUSDT','5m');self.assertTrue(fetched.wait(1))
                deadline=time.monotonic()+1
                while cache._entries['BTCUSDT','5m']['bar']['client']['close']!=12 and time.monotonic()<deadline:time.sleep(.001)
                self.assertEqual(cache._entries['BTCUSDT','5m']['bar']['client']['close'],12)
                release.set();cache.close()
                self.assertEqual(cache._entries['BTCUSDT','5m']['bar']['client']['close'],12)
        finally:release.set();cache.close()

    def test_slow_fetch_is_nonblocking_and_deduplicated(self):
        entered=threading.Event();release=threading.Event();calls=[]
        def fetch(symbol,interval):
            calls.append((symbol,interval));entered.set();release.wait(3);return raw()
        cache=FormingCandleCache(fetch,poll_seconds=10000,wall_clock=lambda:100)
        try:
            first=cache.snapshot('BTCUSDT','1m')
            self.assertEqual(first['status'],'loading')
            self.assertTrue(entered.wait(1))
            self.assertIsNone(cache.snapshot('BTCUSDT','1m')['bar'])
            self.assertEqual(len(calls),1)
        finally:
            release.set();cache.close()
        snapshot=cache.snapshot('BTCUSDT','1m')
        self.assertEqual(snapshot['status'],'live')
        self.assertTrue(snapshot['bar']['provisional'])
        self.assertEqual(snapshot['bar']['client']['close'],11)
        self.assertIsNone(snapshot['bar']['features'])
        self.assertIsNone(snapshot['bar']['adcn'])

    def test_expired_snapshot_is_not_labelled_live(self):
        clock=[0];wall=[100]
        cache=FormingCandleCache(lambda *_:raw(),poll_seconds=10000,
            clock=lambda:clock[0],wall_clock=lambda:wall[0])
        cache.snapshot('BTCUSDT','1m');cache.close()
        self.assertEqual(cache.snapshot('BTCUSDT','1m')['status'],'live')
        clock[0]=10
        self.assertIsNone(cache.snapshot('BTCUSDT','1m')['bar'])

    def test_closed_exchange_bar_is_not_exposed_as_forming(self):
        cache=FormingCandleCache(lambda *_:raw(),poll_seconds=10000,wall_clock=lambda:130)
        cache.snapshot('BTCUSDT','1m');cache.close()
        self.assertIsNone(cache.snapshot('BTCUSDT','1m')['bar'])

    def test_upstream_failure_is_reported_without_raising_in_history_handler(self):
        def fail(*_):raise OSError('upstream unavailable')
        cache=FormingCandleCache(fail,poll_seconds=10000,wall_clock=lambda:100)
        cache.snapshot('BTCUSDT','1m');cache.close()
        result=cache.snapshot('BTCUSDT','1m')
        self.assertEqual(result['status'],'unavailable')
        self.assertIn('upstream unavailable',result['error'])
