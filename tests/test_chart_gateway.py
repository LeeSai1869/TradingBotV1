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
