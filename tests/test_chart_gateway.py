"""Exercise the joined gateway using disposable, real SQLite databases."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import urlopen
from unittest.mock import patch
from http.server import HTTPServer

from Section_1_Global_Core.memory_storage.Storage import db, klines_store, features_store, adcn_store
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader
from Section_11_UI_UX.server import routes, ui_server


class ChartGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for module, name in [(klines_store, 'klines'), (features_store, 'features'),
                             (adcn_store, 'adcn'), (downloader, 'klines')]:
            patcher = patch.object(module, 'DB_PATH', Path(self.temp.name) / f'{name}.db')
            patcher.start()
            self.addCleanup(patcher.stop)
        downloader.open_db().close()
        db.write_klines([self.candle('BTCUSDT', t) for t in (60000, 120000, 180000)])
        db.write_features([dict(symbol='BTCUSDT', interval='1m', open_time=120000, ema50=42)])
        db.write_adcn([dict(symbol='BTCUSDT', interval='1m', open_time=180000,
                            signal_type='BUY', final_score=73)])

    @staticmethod
    def candle(symbol, t):
        return dict(symbol=symbol, interval='1m', open_time=t, close_time=t+59999,
                    open=10, high=12, low=9, close=11, volume=5)

    def test_missing_derived_rows_preserve_canonical_candles(self):
        state = db.read_state_range('BTCUSDT', '1m', 60000, 180001)
        self.assertEqual([b['open_time'] for b in state], [60000,120000,180000])
        self.assertIsNone(state[0]['features'])
        self.assertIsNone(state[0]['adcn'])
        self.assertEqual(state[1]['features']['ema50'], 42)
        self.assertEqual(state[2]['adcn']['signal_type'], 'BUY')

    def test_same_time_in_another_market_does_not_leak_into_join(self):
        db.write_features([dict(symbol='SUIUSDT', interval='1m', open_time=60000, ema50=99)])
        state = db.read_state_range('BTCUSDT', '1m', 60000, 120000)
        self.assertEqual(len(state), 1)
        self.assertIsNone(state[0]['features'])

    def test_chart_packet_aligns_seconds_and_milliseconds(self):
        status, packet = routes.handle_get('/api/chart_window',
            'symbol=BTCUSDT&interval=1m&start=60000&end=180001', None)
        self.assertEqual(status, 200)
        self.assertEqual([k['time'] for k in packet['klines']], [60,120,180])
        self.assertEqual(packet['features'][0]['time'], 120)
        self.assertEqual(packet['flags_history'][0]['bar_time'], 180000)

    def test_paged_bars_are_unified_and_cursor_is_exclusive(self):
        packet = db.read_state_page('BTCUSDT', '1m', 2)
        self.assertEqual([b['time'] for b in packet['bars']], [120, 180])
        self.assertEqual(packet['next_before'], 120000)
        self.assertEqual(packet['bars'][0]['features']['ema50'], 42)
        self.assertEqual(packet['bars'][1]['adcn']['signal_type'], 'BUY')
        older = db.read_state_page('BTCUSDT', '1m', 2, before=packet['next_before'])
        self.assertEqual([b['time'] for b in older['bars']], [60])
        self.assertIsNone(older['next_before'])
        self.assertIsNone(older['bars'][0]['features'])
        self.assertIsNone(older['bars'][0]['adcn'])

    def test_exact_thousand_is_independent_of_wall_clock_and_gaps(self):
        rows = [self.candle('SUIUSDT', 1000000 + i*120000) for i in range(1500)]
        db.write_klines(rows)
        latest = db.read_state_page('SUIUSDT', '1m', 1000)
        self.assertEqual(len(latest['bars']), 1000)
        self.assertEqual(latest['bars'][0]['open_time'], rows[500]['open_time'])
        older = db.read_state_page('SUIUSDT', '1m', 500, before=latest['next_before'])
        self.assertEqual(len(older['bars']), 500)
        self.assertIsNone(older['next_before'])
        self.assertEqual(older['bars'][-1]['open_time'], rows[499]['open_time'])

    def test_calendar_month_pages_use_stored_keys(self):
        from datetime import datetime, timezone
        rows = []
        for month in (1,2,3,5):
            row = self.candle('BTCUSDT', int(datetime(2024,month,1,tzinfo=timezone.utc).timestamp()*1000))
            row['interval'] = '1M'
            rows.append(row)
        db.write_klines(rows)
        packet = db.read_state_page('BTCUSDT', '1M', 3)
        self.assertEqual([b['open_time'] for b in packet['bars']], [r['open_time'] for r in rows[1:]])

    def test_ui_bar_routes_never_contact_binance(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('unexpected upstream request')):
            status, packet = routes.handle_get('/api/bars', 'symbol=BTCUSDT&interval=1m&limit=2', None)
            self.assertEqual(status,200)
            self.assertEqual(len(packet['bars']),2)
            self.assertNotIn('klines',packet)
            self.assertNotIn('features',packet)
            status, _ = routes.handle_get('/api/live_candle','symbol=BTCUSDT&interval=1m',None)
            self.assertEqual(status,410)
            status, _ = routes.handle_get('/api/symbol_meta','symbol=BTCUSDT',None)
            self.assertEqual(status,200)

    def test_forming_snapshot_is_in_latest_packet_only(self):
        snapshot = {"bar": {"time": 240, "provisional": True}, "status": "live"}
        with patch.object(routes.live_candle, 'get_snapshot', return_value=snapshot) as live:
            status, packet = routes.handle_get('/api/bars',
                'symbol=BTCUSDT&interval=1m&live=1', None)
            self.assertEqual(status,200)
            self.assertEqual(packet['live'],snapshot)
            self.assertEqual(len(packet['bars']),3)
            live.reset_mock()
            status, packet = routes.handle_get('/api/bars',
                'symbol=BTCUSDT&interval=1m&limit=2&before=180000&live=1',None)
            self.assertEqual(status,200)
            self.assertNotIn('live',packet)
            live.assert_not_called()

    def test_invalid_cursor_and_page_size_are_rejected(self):
        for query in ['limit=0','limit=1001','before=wrong','limit=wrong']:
            status,_ = routes.handle_get('/api/bars', 'symbol=BTCUSDT&interval=1m&'+query,None)
            self.assertEqual(status,400)

    def test_real_feature_builder_reaches_the_joined_gateway(self):
        from Section_4_Features.processor import _compute_and_write_one
        rows = []
        for i in range(510):
            candle = self.candle('SUIUSDT', 1700000000000 + i * 60000)
            for key in ('open', 'high', 'low', 'close'):
                candle[key] += i * 0.01
            rows.append(candle)
        db.write_klines(rows)
        t = rows[-1]['open_time']
        self.assertEqual(_compute_and_write_one('SUIUSDT', '1m', t), 1)
        state = db.read_state_range('SUIUSDT', '1m', t, t+1)
        self.assertIsNotNone(state[0]['features']['ema50'])
        self.assertIsNone(state[0]['adcn'])

    def test_real_http_serves_chart_and_complete_memory_packet(self):
        server = HTTPServer(('127.0.0.1',0), ui_server.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            with urlopen(base + '/') as r:
                self.assertIn(b'/web_root/app.js', r.read())
            with urlopen(base + '/api/chart_window?symbol=BTCUSDT&interval=1m&start=60000&end=180001') as r:
                packet = json.load(r)
            self.assertEqual(len(packet['klines']),3)
            self.assertEqual(packet['flags_history'][0]['signal_type'],'BUY')
            with urlopen(base + '/api/flags_current?symbol=BTCUSDT&interval=1m') as r:
                self.assertEqual(json.load(r)['final_score'],73)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
