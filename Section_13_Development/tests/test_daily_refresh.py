import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
from Section_1_Global_Core.Symbols import daily_refresh,symbol_proposer


class DailyRefreshTests(unittest.TestCase):
    def test_optional_key_supports_environment_file_and_public_requests(self):
        import io
        with TemporaryDirectory() as directory,patch.object(symbol_proposer,'_ENV',Path(directory)/'.env'),patch.dict(symbol_proposer.os.environ,{},clear=True):
            self.assertIsNone(symbol_proposer._key())
            symbol_proposer._ENV.write_text('COINGECKO_API_KEY="file-key"\n')
            self.assertEqual(symbol_proposer._key(),'file-key')
            with patch.dict(symbol_proposer.os.environ,{'COINGECKO_API_KEY':'environment-key'}):
                self.assertEqual(symbol_proposer._key(),'environment-key')
            symbol_proposer._ENV.write_text('# no key configured\n')
            self.assertIsNone(symbol_proposer._key())
            for key in (None,'configured-key'):
                with patch.object(symbol_proposer.urllib.request,'urlopen',return_value=io.BytesIO(b'[]')) as request:
                    self.assertEqual(symbol_proposer._fetch_cg_page(key,1),[])
                    headers={k.lower():v for k,v in request.call_args.args[0].header_items()}
                    self.assertEqual(headers.get('x-cg-demo-api-key'),key)

    def test_incomplete_public_list_preserves_existing_registry(self):
        with patch.object(symbol_proposer,'_key',return_value=None),patch.object(symbol_proposer,'_fetch_binance_usdt_pairs',return_value=set()),patch.object(symbol_proposer,'_fetch_cg_page',return_value=[]),patch.object(symbol_proposer,'_write') as write:
            with self.assertRaisesRegex(RuntimeError,'previous top-50 registry retained'):symbol_proposer.propose(notify=False)
            write.assert_not_called()

    def test_success_persists_daily_deadline_and_failure_retries_without_registry_change(self):
        with TemporaryDirectory() as directory,patch.object(daily_refresh,'STATE',Path(directory)/'state.json'),patch.object(symbol_proposer,'propose') as propose:
            daily_refresh._run()
            propose.assert_called_once_with(notify=False)
            saved=daily_refresh.STATE.read_text()
            self.assertGreater(daily_refresh._next_attempt,time.time()+86000)
            propose.side_effect=RuntimeError('network offline')
            daily_refresh._run()
            self.assertEqual(daily_refresh.STATE.read_text(),saved)
            self.assertLess(daily_refresh._next_attempt,time.time()+3601)

    def test_tick_does_not_start_worker_before_persisted_deadline(self):
        with TemporaryDirectory() as directory,patch.object(daily_refresh,'STATE',Path(directory)/'state.json'),patch.object(daily_refresh,'_next_attempt',0),patch.object(daily_refresh,'_worker',None),patch.object(daily_refresh.threading,'Thread') as worker:
            import datetime
            daily_refresh.STATE.write_text(json.dumps({'last_success':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
            daily_refresh.tick();worker.assert_not_called()
