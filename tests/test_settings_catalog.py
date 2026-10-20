"""Settings groups preserve every registry entry without changing registry data."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Section_11_UI_UX.server import settings_catalog, routes


class SettingsCatalogTests(unittest.TestCase):
    def test_categories_keep_status_and_eligibility_separate(self):
        source = dict(approved=[dict(symbol='BTCUSDT'), dict(symbol='OLDUSDT')],
                      top50=[dict(symbol='BTCUSDT')],
                      disapproved=[dict(symbol='MANUAL', reason='manual'),
                                   dict(symbol='DOGEUSDT', reason='auto:meme'),
                                   dict(symbol='USDCUSDT', reason='auto:stablecoin'),
                                   dict(symbol='MISSING', reason='not_on_binance'),
                                   dict(symbol='RANK', reason='auto:below_top50')],
                      pending=[dict(symbol='NEW')], staged=[dict(symbol='STAGED')])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'symbols.json'
            original = json.dumps(source)
            path.write_text(original)
            with patch.object(settings_catalog, 'REGISTRY_PATH', path):
                status, result = routes.handle_get('/api/settings/coins', '', None)
            self.assertEqual(status, 200)
            self.assertEqual([r['symbol'] for r in result['approved']], ['BTCUSDT'])
            self.assertEqual([r['symbol'] for r in result['inactive']], ['OLDUSDT'])
            self.assertEqual([r['symbol'] for r in result['disapproved']], ['MANUAL','RANK'])
            self.assertEqual([r['symbol'] for r in result['ineligible']], ['DOGEUSDT','USDCUSDT','MISSING'])
            self.assertEqual(sum(map(len, result.values())), 9)
            self.assertEqual(path.read_text(), original)

    def test_missing_registry_is_reported_without_creating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'missing.json'
            with patch.object(settings_catalog, 'REGISTRY_PATH', path):
                status, result = routes.handle_get('/api/settings/coins', '', None)
            self.assertEqual(status, 503)
            self.assertIn('error', result)
            self.assertFalse(path.exists())
