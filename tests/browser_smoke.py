"""Run against real chart JS and disposable SQLite data, never live market data.

PYTHONPATH=. python3 tests/browser_smoke.py /path/to/lightweight-charts.standalone.production.js
Requires Playwright and Chromium; the chart library is supplied from its verified npm package.
"""
import math
from pathlib import Path
import sys
import tempfile
import threading
import time
from http.server import HTTPServer
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from Section_1_Global_Core.memory_storage.Storage import db, klines_store, features_store, adcn_store
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader
from Section_11_UI_UX.server import ui_server, symbol_meta, live_candle


def run(library):
    with tempfile.TemporaryDirectory() as directory:
        from contextlib import ExitStack
        with ExitStack() as stack:
            for module, name in [(klines_store,'klines'),(features_store,'features'),
                                 (adcn_store,'adcn'),(downloader,'klines')]:
                stack.enter_context(patch.object(module,'DB_PATH',Path(directory)/f'{name}.db'))
            downloader.open_db().close()
            for symbol in ['BTCUSDT','SUIUSDT']:
                for interval, step in [('1m',60000),('15m',900000)]:
                    end = int(time.time()*1000)//step*step
                    klines=[]; features=[]; decisions=[]
                    for i in range(2200):
                        t = end-(2200-i)*step
                        value=100 + i*.01 + math.sin(i/10)
                        klines.append(dict(symbol=symbol,interval=interval,open_time=t,
                            close_time=t+step-1,open=value,high=value+2,low=value-1,close=value+1,volume=10))
                        features.append(dict(symbol=symbol,interval=interval,open_time=t,ema50=value))
                        if i%100 == 0:
                            decisions.append(dict(symbol=symbol,interval=interval,open_time=t,signal_type='BUY',final_score=73))
                    db.write_klines(klines); db.write_features(features); db.write_adcn(decisions)
            stack.enter_context(patch.object(symbol_meta,'_CACHE',{
                'BTCUSDT':dict(precision=2,tickSize='0.01'), 'SUIUSDT':dict(precision=4,tickSize='0.0001')}))
            def forming(symbol, interval):
                step=60000 if interval=='1m' else 900000
                return dict(time=int(time.time()*1000)//step*step//1000,open=125,high=127,low=124,close=126,volume=5)
            stack.enter_context(patch.object(live_candle,'fetch_forming_candle',forming))
            class QuietHandler(ui_server.Handler):
                def log_message(self,*args): pass
            server=HTTPServer(('127.0.0.1',0),QuietHandler)
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            try:
                with sync_playwright() as p:
                    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
                    page=browser.new_page(viewport={'width':1400,'height':900})
                    failures=[]
                    page.on('pageerror',lambda e: failures.append(str(e)))
                    page.on('console',lambda m: failures.append(m.text) if m.type=='error' else None)
                    page.route('https://unpkg.com/**',lambda route: route.fulfill(path=str(library),content_type='application/javascript'))
                    page.goto(f'http://127.0.0.1:{server.server_port}/')
                    page.wait_for_function('window.DataCache && !DataCache.loading && DataCache.klines.length >= 999 && DataCache.readyOlder')
                    page.wait_for_timeout(200)
                    assert page.locator('#chart canvas').count() > 0
                    assert page.evaluate('DataCache.features.length') == page.evaluate('DataCache.klines.length')
                    # Rapid selection changes exercise the real app coordinator.
                    page.select_option('#symbol','SUIUSDT')
                    page.select_option('#interval','1m')
                    page.select_option('#symbol','BTCUSDT')
                    page.wait_for_function('!DataCache.loading && DataCache.symbol === "BTCUSDT" && DataCache.timeframe === "1m" && DataCache.readyOlder')
                    page.wait_for_timeout(200)
                    # Trigger an actual historical block rotation.
                    before=page.evaluate('DataCache.klines[0].time')
                    page.evaluate('Canvas.chart.timeScale().setVisibleLogicalRange({from:50,to:350})')
                    page.wait_for_function('(t) => DataCache.klines[0].time < t',arg=before)
                    page.wait_for_timeout(200)
                    assert not page.evaluate('DataCache.atLiveEdge')
                    assert page.evaluate('DataCache.features.length') == page.evaluate('DataCache.klines.length')
                    # Reload returns to the selected market's current window.
                    page.click('#reload')
                    page.wait_for_function('(t) => !DataCache.loading && DataCache.atLiveEdge && DataCache.klines[0].time === t',arg=before)
                    page.wait_for_timeout(200)
                    assert not failures, failures
                    browser.close()
                    print('PASS: real chart rendering, combined memory overlays, rapid selection, historical rotation and reload; no browser errors')
            finally:
                server.shutdown(); thread.join(); server.server_close()


if __name__=='__main__':
    run(Path(sys.argv[1]).resolve())
