"""Full-flow regression with real chart JS and disposable stored-bar fixtures.

PYTHONPATH=. python3 tests/browser_smoke.py /path/to/lightweight-charts.standalone.production.js
Uses installed Playwright and /usr/bin/chromium. No live market requests.
"""
import asyncio
from contextlib import ExitStack
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
from http.server import HTTPServer
from unittest.mock import patch

from playwright.async_api import async_playwright
from Section_1_Global_Core.memory_storage.Storage import db, klines_store, features_store, adcn_store
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader
from Section_11_UI_UX.server import routes, ui_server


async def exercise(base, library):
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                          args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width':2560,'height':1440})
        failures = []
        requests = []
        page.on('pageerror',lambda e: failures.append(str(e)))
        page.on('console',lambda m: failures.append(m.text) if m.type == 'error' else None)
        page.on('request',lambda r: requests.append(r.url))
        source = library.read_text() + '''
;window.markerAudit={created:0,updated:0};
const createMarkersOriginal=LightweightCharts.createSeriesMarkers;
window.LightweightCharts={...LightweightCharts,createSeriesMarkers:(...args)=>{
 window.markerAudit.created++;
 const wrapper=createMarkersOriginal(...args);
 const update=wrapper.setMarkers.bind(wrapper);
 wrapper.setMarkers=(...rows)=>{window.markerAudit.updated++;return update(...rows);};
 return wrapper;
}};
'''
        await page.route('https://unpkg.com/**', lambda route:route.fulfill(
            body=source,content_type='application/javascript'))
        async def slow_history(route):
            if 'before=' in route.request.url:
                await asyncio.sleep(.15)
            await route.continue_()
        await page.route('**/api/bars?*',slow_history)
        await page.goto(base)
        await page.wait_for_function('window.DataCache && !DataCache.loading && DataCache.bars.length === 2000 && !DataCache._olderPromise')
        await settle(page)
        assert await page.evaluate('DataCache.activeBars.length') == 1000
        visible = await page.evaluate('Canvas.chart.timeScale().getVisibleLogicalRange()')
        assert abs(visible['to']-visible['from']-999) < .01, visible
        assert await page.evaluate('DataCache.latestBar.time') == 1781653500
        assert await page.locator('#chart canvas').count() > 0
        assert await page.evaluate('DataCache.bars.every(b => b.client && b.features && "adcn" in b)')
        print('PASS: exactly 1000 initially visible, old stored history, combined bar records',flush=True)

        # A -> B -> C... across 10,000 bars. Every prepend must keep the
        # requested visible timestamps and center candle pixel coordinate.
        initial = await page.evaluate('Canvas.chart.timeScale().getVisibleRange()')
        initial_center = await page.evaluate('() => {const r=Canvas.chart.timeScale().getVisibleLogicalRange();return DataCache.bars[Math.floor((r.from+r.to)/2)].time;}')
        for i in range(20):
            expected = await page.evaluate('''() => {
                const ts=Canvas.chart.timeScale(), r=ts.getVisibleLogicalRange();
                const from=Math.round(r.from)-500, to=Math.round(r.to)-500;
                const bars=DataCache.bars;
                const middle=bars[Math.floor((from+to)/2)].time;
                ts.setVisibleLogicalRange({from,to});
                return {from:bars[from].time,to:bars[to].time,middle,count:bars.length};
            }''')
            await settle(page)
            before_position = await page.evaluate('(t) => Canvas.chart.timeScale().timeToCoordinate(t)',expected['middle'])
            await page.wait_for_function('(n) => DataCache.bars.length === n+500 && !DataCache._olderPromise',arg=expected['count'])
            await settle(page)
            actual = await page.evaluate('Canvas.chart.timeScale().getVisibleRange()')
            # Time-range endpoints round fractional edge candles. Pixel
            # continuity below is stricter than comparing rounded endpoints.
            assert abs(actual['from']-expected['from']) <= 900 and abs(actual['to']-expected['to']) <= 900, (i,expected,actual)
            # The same timestamp must remain centered; no transition jump.
            position = await page.evaluate('(t) => Canvas.chart.timeScale().timeToCoordinate(t)',expected['middle'])
            bounds = await page.evaluate('Canvas.chart.timeScale().width()')
            assert abs(position-before_position) < .1, (i,position,before_position)
            assert abs(position-bounds/2) < 5, (i,position,bounds)
        walked = await page.evaluate('Canvas.chart.timeScale().getVisibleRange()')
        walked_center = await page.evaluate('() => {const r=Canvas.chart.timeScale().getVisibleLogicalRange();return DataCache.bars[Math.floor((r.from+r.to)/2)].time;}')
        assert initial_center-walked_center == 10000*900
        print('PASS: 20 successive 500-bar pages, 10000 candles back, stable timestamps and center position',flush=True)

        # All visited pages remain cached. Reverse to newest without refetch.
        request_count = len([u for u in requests if '/api/bars?' in u])
        for _ in range(20):
            await page.evaluate('''() => {const ts=Canvas.chart.timeScale(),r=ts.getVisibleLogicalRange();
                ts.setVisibleLogicalRange({from:r.from+500,to:r.to+500});}''')
            await settle(page)
        returned = await page.evaluate('Canvas.chart.timeScale().getVisibleRange()')
        assert abs(returned['from']-initial['from']) <= 900 and abs(returned['to']-initial['to']) <= 900
        assert len([u for u in requests if '/api/bars?' in u]) == request_count
        print('PASS: reverse all 10000 candles using cached data, no history requests',flush=True)

        # Delayed next block: stop beyond the boundary and make sure its
        # arrival fills the view and starts the following page on its own.
        gate=asyncio.Event(); entered=asyncio.Event(); held=False
        async def delayed(route):
            nonlocal held
            if 'before=' in route.request.url and not held:
                held=True;entered.set();await gate.wait()
            await route.continue_()
        await page.route('**/api/bars?*',delayed)
        oldest_before=await page.evaluate('DataCache.bars[0].time')
        await page.evaluate('Canvas.chart.timeScale().setVisibleLogicalRange({from:-100,to:899})')
        await asyncio.wait_for(entered.wait(),5)
        await settle(page)
        count_before=await page.evaluate('DataCache.bars.length')
        pending_range=await page.evaluate('Canvas.chart.timeScale().getVisibleLogicalRange()')
        gate.set()
        await page.wait_for_function('(n) => DataCache.bars.length >= n+1000 && !DataCache._olderPromise',arg=count_before)
        await settle(page)
        arrived=await page.evaluate('Canvas.chart.timeScale().getVisibleRange()')
        assert abs(arrived['from']-(oldest_before-100*900)) <= 900, arrived
        arrived_range=await page.evaluate('Canvas.chart.timeScale().getVisibleLogicalRange()')
        added=await page.evaluate('DataCache.bars.length')-count_before
        assert abs(arrived_range['from']-(pending_range['from']+added)) < .0001
        assert abs(arrived_range['to']-(pending_range['to']+added)) < .0001
        print('PASS: stationary boundary resumes on arrival and prepares following page',flush=True)
        await page.unroute('**/api/bars?*',delayed)

        # Reverse direction while an older page is still in flight.
        gate=asyncio.Event();entered=asyncio.Event();held=False
        await page.route('**/api/bars?*',delayed)
        await page.evaluate('Canvas.chart.timeScale().setVisibleLogicalRange({from:500,to:1499})')
        await asyncio.wait_for(entered.wait(),5)
        await page.evaluate('Canvas.chart.timeScale().setVisibleLogicalRange({from:1000,to:1999})')
        await settle(page)
        reverse_view=await page.evaluate('Canvas.chart.timeScale().getVisibleRange()')
        reverse_anchor=await page.evaluate('() => {const t=DataCache.bars[1500].time;return {time:t,x:Canvas.chart.timeScale().timeToCoordinate(t)};}')
        gate.set()
        await page.wait_for_function('!DataCache._olderPromise')
        await settle(page)
        reverse_result=await page.evaluate('Canvas.chart.timeScale().getVisibleRange()')
        assert abs(reverse_result['from']-reverse_view['from']) <= 900
        reverse_x=await page.evaluate('(t)=>Canvas.chart.timeScale().timeToCoordinate(t)',reverse_anchor['time'])
        assert abs(reverse_x-reverse_anchor['x']) < .1
        await page.unroute('**/api/bars?*',delayed)
        print('PASS: direction reversal during pending prefetch preserves latest user view',flush=True)

        # Config selection is renderer-only and never creates another
        # marker primitive or requests a separate feature dataset.
        audit_before=await page.evaluate('markerAudit.created')
        await page.evaluate('''() => {
            Composer.config.display={ema50:false,markers:false};
            Composer.updateAll(Canvas.chart,DataCache,'config');
            Composer.config.display={};
            for(let i=0;i<10;i++) Composer.updateAll(Canvas.chart,DataCache,'audit');
        }''')
        await settle(page)
        assert audit_before == 1 and await page.evaluate('markerAudit.created') == 1
        assert await page.evaluate('markerAudit.updated') >= 10
        print('PASS: one marker wrapper across navigation, config changes and redraws',flush=True)

        # Stale initial loads still cannot contaminate a new selection.
        await page.select_option('#symbol','SUIUSDT')
        await page.select_option('#interval','1m')
        await page.select_option('#symbol','BTCUSDT')
        await page.wait_for_function('!DataCache.loading && DataCache.symbol === "BTCUSDT" && DataCache.timeframe === "1m" && DataCache.bars.length === 2000 && !DataCache._olderPromise')
        await settle(page)
        assert await page.evaluate('DataCache.bars.every(b=>b.symbol === "BTCUSDT" && b.interval === "1m")')
        await page.click('#reload')
        await page.wait_for_function('!DataCache.loading && DataCache.bars.length === 2000 && !DataCache._olderPromise')
        await settle(page)
        assert await page.evaluate('DataCache.activeBars.length') == 1000
        # The ingestion process may continue writing locally. Follow new
        # stored bars only at the newest edge, never while browsing history.
        def append_bar(t):
            db.write_klines([dict(symbol='BTCUSDT',interval='1m',open_time=t,
                close_time=t+59999,open=123,high=125,low=122,close=124,volume=5)])
            db.write_features([dict(symbol='BTCUSDT',interval='1m',open_time=t,ema50=123)])
            db.write_adcn([dict(symbol='BTCUSDT',interval='1m',open_time=t,signal_type='SELL',final_score=88)])
        append_bar(1781654400000)
        await page.evaluate('DataCache.refreshStored()')
        await settle(page)
        assert await page.evaluate('DataCache.latestBar.time') == 1781654400
        assert await page.evaluate('Canvas.chart.timeScale().getVisibleRange().to') == 1781654400
        assert 'SELL' in await page.locator('#flags-signal').text_content()
        await page.evaluate('Canvas.chart.timeScale().setVisibleLogicalRange({from:700,to:1699})')
        await settle(page)
        historical=await page.evaluate('Canvas.chart.timeScale().getVisibleRange()')
        count_before_refresh=len([u for u in requests if '/api/bars?' in u])
        append_bar(1781654460000)
        assert await page.evaluate('DataCache.refreshStored()') is False
        assert await page.evaluate('Canvas.chart.timeScale().getVisibleRange()') == historical
        assert len([u for u in requests if '/api/bars?' in u]) == count_before_refresh
        await page.evaluate('''() => {const n=DataCache.bars.length;
            Canvas.chart.timeScale().setVisibleLogicalRange({from:n-1000,to:n-1});}''')
        await settle(page)
        await page.evaluate('DataCache.refreshStored()')
        await settle(page)
        assert await page.evaluate('DataCache.latestBar.time') == 1781654460
        # Derived state can arrive/change without a new candle.
        before_count=await page.evaluate('DataCache.bars.length')
        db.write_features([dict(symbol='BTCUSDT',interval='1m',open_time=1781654460000,ema50=99)])
        await page.evaluate('DataCache.refreshStored()')
        await settle(page)
        assert await page.evaluate('DataCache.latestBar.features.ema50') == 99
        assert await page.evaluate('DataCache.bars.length') == before_count
        assert await page.evaluate('markerAudit.created') == 1
        print('PASS: local ingestion updates follow newest edge, pause in history and update derived state in the same bar',flush=True)
        assert not failures, failures
        forbidden=['binance.com','/api/live_candle','/api/symbol_meta','/api/flags_current','/api/chart_window']
        assert not [u for u in requests if any(path in u for path in forbidden)], requests
        print('PASS: rapid selection/reload, no browser errors, no Binance or separate candle/EMA/flags requests',flush=True)
        await browser.close()


async def settle(page):
    await page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(resolve))))')


def run(library):
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        for module,name in [(klines_store,'klines'),(features_store,'features'),
                            (adcn_store,'adcn'),(downloader,'klines')]:
            stack.enter_context(patch.object(module,'DB_PATH',Path(directory)/f'{name}.db'))
        downloader.open_db().close()
        for symbol,interval,step,count in [('BTCUSDT','15m',900000,14000),
                ('BTCUSDT','1m',60000,2200),('SUIUSDT','1m',60000,2200),('SUIUSDT','15m',900000,2200)]:
            # June 17, 2026: intentionally far behind the execution clock.
            end=1781654400000
            klines=[];features=[];decisions=[]
            for i in range(count):
                t=end-(count-i)*step;value=100+i*.01+math.sin(i/10)
                klines.append(dict(symbol=symbol,interval=interval,open_time=t,close_time=t+step-1,
                    open=value,high=value+2,low=value-1,close=value+1,volume=10))
                features.append(dict(symbol=symbol,interval=interval,open_time=t,ema50=value))
                if i%100==0:decisions.append(dict(symbol=symbol,interval=interval,open_time=t,signal_type='BUY',final_score=73))
            db.write_klines(klines);db.write_features(features);db.write_adcn(decisions)
        config=json.loads(routes.UI_CONFIG.read_text())
        config.update(stored_refresh_ms=0,price_precision={'BTCUSDT':2,'SUIUSDT':4})
        stack.enter_context(patch.object(routes,'read_ui_config',lambda:config))
        class QuietHandler(ui_server.Handler):
            def log_message(self,*args):pass
        server=HTTPServer(('127.0.0.1',0),QuietHandler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            asyncio.run(exercise(f'http://127.0.0.1:{server.server_port}',library))
        finally:
            server.shutdown();thread.join();server.server_close()


if __name__=='__main__':
    run(Path(sys.argv[1]).resolve())
