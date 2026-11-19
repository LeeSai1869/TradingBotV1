"""A blocked optional HUD or idle browser connection cannot stall the app."""
from concurrent.futures import ThreadPoolExecutor
import json
import socket
import tempfile
from pathlib import Path
import threading
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from Section_11_UI_UX.server import ui_server, routes
from Section_1_Global_Core import data_policy


class UiAvailabilityTests(unittest.TestCase):
    def setUp(self):
        identity=patch.object(routes.admin_routes,'user',return_value={'role':'user'})
        identity.start();self.addCleanup(identity.stop)
        class Quiet(ui_server.Handler):
            def log_message(self,*args):pass
        self.server=ui_server.ThreadingHTTPServer(('127.0.0.1',0),Quiet)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close)
        self.base=f'http://127.0.0.1:{self.server.server_port}'

    def close(self):
        self.server.shutdown();self.thread.join();self.server.server_close()

    def get(self,path):
        with urlopen(self.base+path,timeout=2) as response:return response.read()

    def test_idle_browser_socket_does_not_block_static_or_session(self):
        connection=socket.create_connection(self.server.server_address,timeout=2)
        self.addCleanup(connection.close)
        self.assertIn(b'web_root/app.js',self.get('/'))
        self.assertEqual(json.loads(self.get('/api/session'))['role'],'user')

    def test_waiting_hud_does_not_block_chart_or_catalog(self):
        entered=threading.Event();release=threading.Event()
        def hud(path,query):
            if path=='/api/hud':entered.set();release.wait(3);return 200,{'columns':[]}
            if path=='/api/hud/catalog':return 200,{'fields':{}}
            return None,None
        with patch.object(routes.hud,'handle_get',side_effect=hud),patch.object(routes.db,'read_state_page',return_value={'bars':[],'next_before':None}),patch.object(routes.data_policy,'enabled',return_value=False):
            with ThreadPoolExecutor(1) as pool:
                pending=pool.submit(self.get,'/api/hud')
                try:
                    self.assertTrue(entered.wait(1))
                    self.assertEqual(json.loads(self.get('/api/hud/catalog')),{'fields':{}})
                    self.assertEqual(json.loads(self.get('/api/bars?symbol=BTCUSDT&interval=1m'))['bars'],[])
                finally:release.set()
                pending.result()

    def test_busy_and_failed_api_return_json_instead_of_dropped_connection(self):
        for error,status in ((TimeoutError('busy'),503),(RuntimeError('bad HUD'),500)):
            with patch.object(routes.hud,'handle_get',side_effect=error):
                with self.assertRaises(HTTPError) as result:self.get('/api/hud')
            self.assertEqual(result.exception.code,status)
            self.assertIn('error',json.load(result.exception))
        self.assertEqual(json.loads(self.get('/api/session'))['role'],'user')

    def test_real_data_lock_wait_is_bounded_and_can_recover(self):
        def competing_writer():
            with data_policy.locked(timeout=.05):pass
        with tempfile.TemporaryDirectory() as directory,patch.object(data_policy,'LOCK_FILE',Path(directory)/'lock'),ThreadPoolExecutor(1) as pool:
            with data_policy.locked():
                start=time.monotonic()
                with self.assertRaises(TimeoutError):
                    pool.submit(competing_writer).result(timeout=1)
                self.assertLess(time.monotonic()-start,.5)
            pool.submit(competing_writer).result(timeout=1)

    def test_chart_reads_while_runner_owns_writer_lock(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(data_policy,'LOCK_FILE',Path(directory)/'lock'):
            with data_policy.locked():
                with patch.object(routes.db,'read_state_page',return_value={'bars':[],'next_before':None}):
                    self.assertEqual(json.loads(self.get('/api/bars?symbol=BTCUSDT&interval=1m'))['bars'],[])
                self.assertEqual(json.loads(self.get('/api/session'))['role'],'user')

    def test_only_destructive_deletion_blocks_chart_snapshot(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(data_policy,'LOCK_FILE',Path(directory)/'lock'):
            with data_policy.snapshot_guard(exclusive=True):
                with self.assertRaises(HTTPError) as result:
                    self.get('/api/bars?symbol=BTCUSDT&interval=1m')
                self.assertEqual(result.exception.code,503)
                self.assertEqual(result.exception.headers['Retry-After'],'1')
                self.assertEqual(json.loads(self.get('/api/session'))['role'],'user')
