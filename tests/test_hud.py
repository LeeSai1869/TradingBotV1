import unittest
from unittest.mock import patch
import test_chart_gateway as fixtures
from Section_11_UI_UX.server import hud
from Section_1_Global_Core.memory_storage.Storage import db


class HudTests(unittest.TestCase):
    setUp = fixtures.ChartGatewayTests.setUp
    candle = staticmethod(fixtures.ChartGatewayTests.candle)

    def test_comparison_uses_latest_joined_bar_and_keeps_missing_values(self):
        db.write_features([dict(symbol='BTCUSDT',interval='1m',open_time=180000,rsi=61,di_direction=-4)])
        with patch.object(hud.time,'time',return_value=240), patch.object(hud.data_policy,'enabled',return_value=True):
            status, result=hud.handle_get('/api/hud','symbol=BTCUSDT&intervals=1m,1h&fields=features.rsi,features.di_direction,adcn.signal_type')
        self.assertEqual(status,200)
        current, empty=result['columns']
        self.assertEqual(current['values'],{'features.rsi':61,'features.di_direction':-4,'adcn.signal_type':'BUY'})
        self.assertEqual(current['open_time'],180000)
        self.assertFalse(current['stale'])
        self.assertIsNone(empty['open_time'])
        self.assertTrue(all(value is None for value in empty['values'].values()))

    def test_inactive_stale_stored_reference_is_labelled(self):
        with patch.object(hud.time,'time',return_value=10000), patch.object(hud.data_policy,'enabled',return_value=False):
            status, result=hud.handle_get('/api/hud','symbol=BTCUSDT&intervals=1m')
        self.assertEqual(status,200)
        self.assertTrue(result['columns'][0]['stale'])
        self.assertFalse(result['columns'][0]['active'])

    def test_validation_rejects_unbounded_or_unknown_requests_before_reading(self):
        for query in ('symbol=BTCUSDT&intervals='+','.join(hud.data_policy.INTERVALS[:9]),
                      'symbol=BTCUSDT&intervals=1m,1m','symbol=BTCUSDT&intervals=garbage',
                      'symbol=BTCUSDT&fields=features.missing','symbol=BTCUSDT&fields='+','.join(list(hud.FIELDS)[:21]),
                      'symbol=../../other'):
            with patch.object(hud.db,'read_state_page') as read:
                self.assertEqual(hud.handle_get('/api/hud',query)[0],400)
                read.assert_not_called()

    def test_eight_timeframes_read_only_one_combined_bar_each(self):
        intervals=hud.data_policy.INTERVALS[:8]
        with patch.object(hud.db,'read_state_page',return_value={'bars':[]}) as read:
            self.assertEqual(hud.handle_get('/api/hud','symbol=BTCUSDT&intervals='+','.join(intervals))[0],200)
        self.assertEqual(read.call_count,8)
        self.assertTrue(all(call.args[2]==1 for call in read.call_args_list))

    def test_live_column_uses_existing_shared_forming_snapshot(self):
        candidate=dict(symbol='BTCUSDT',interval='1m',open_time=240000,provisional=True,
                       client=dict(close=13,close_time=299999),features=dict(rsi=82),adcn=None)
        with patch.object(hud.data_policy,'enabled',return_value=True),patch.object(hud.live_candle,'get_snapshot',return_value={'bar':candidate,'status':'live'}) as snapshot:
            status, packet=hud.handle_get('/api/hud','symbol=BTCUSDT&intervals=1m&fields=client.close,features.rsi&live=1')
        self.assertEqual(status,200)
        self.assertEqual(packet['columns'][0]['values'],{'client.close':13,'features.rsi':82})
        self.assertEqual(packet['columns'][0]['status'],'live provisional candle')
        snapshot.assert_called_once_with('BTCUSDT','1m')
