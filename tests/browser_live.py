"""Live-price browser regression with a controlled upstream snapshot.

PYTHONPATH=. python3 tests/browser_live.py /path/to/lightweight-charts.standalone.production.js
Reuses the isolated database fixture from browser_smoke, never real account data.
"""
from pathlib import Path
import sys
from unittest.mock import patch
from playwright.async_api import async_playwright
from browser_smoke import run, settle, sign_in, db, routes

T = 1781654400000
STEP = 900000


def quote(t, close=130):
    return dict(symbol='BTCUSDT',interval='15m',open_time=t,time=t//1000,provisional=True,
        client=dict(symbol='BTCUSDT',interval='15m',open_time=t,close_time=t+STEP-1,
                    open=125,high=max(131,close+1),low=124,close=close,volume=5),
        features=None,adcn=None)


async def exercise_live(base, library):
    routes.read_ui_config()['live_candle'] = True
    state = {'bar':quote(T),'status':'live','as_of':T+1000,'error':None}
    with patch.object(routes.live_candle,'get_snapshot',lambda *_:dict(state)):
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=await browser.new_page(viewport={'width':2560,'height':1440})
            errors=[];requests=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
            page.on('request',lambda r:requests.append(r.url))
            await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
            await page.goto(base)
            await sign_in(page)
            await page.wait_for_function('window.DataCache && DataCache.bars.length === 2000 && !DataCache._olderPromise && DataCache.formingBar')
            await settle(page)
            assert await page.evaluate('DataCache.formingBar.time') == T//1000
            assert await page.evaluate('DataCache.renderBars.length') == 2001
            await page.evaluate('''async () => {
                const {getSeries}=await import('/overlays/candles/index.js');
                const series=getSeries();window.liveSeries=series;
                window.liveAudit={setData:0,update:0};
                const set=series.setData.bind(series),tick=series.update.bind(series);
                series.setData=(...args)=>{liveAudit.setData++;return set(...args);};
                series.update=(...args)=>{liveAudit.update++;return tick(...args);};
            }''')
            count=db.count_klines('BTCUSDT','15m')
            state['bar']=quote(T,131)
            await page.evaluate('DataCache.refreshStored()')
            await settle(page)
            assert await page.evaluate('liveSeries.data().at(-1).close') == 131
            assert await page.evaluate('liveAudit.update') == 1
            assert await page.evaluate('liveAudit.setData') == 0
            assert db.count_klines('BTCUSDT','15m') == count
            assert await page.evaluate('DataCache.formingBar.features') is None
            print('PASS: live tick updates one point in the combined stream, no history rebuild or permanent writes',flush=True)

            await page.evaluate('Canvas.chart.timeScale().setVisibleLogicalRange({from:700,to:1699})')
            await settle(page)
            historical=await page.evaluate('Canvas.chart.timeScale().getVisibleRange()')
            state['bar']=quote(T,132)
            before=len(requests)
            assert await page.evaluate('DataCache.refreshStored()') is False
            assert await page.evaluate('Canvas.chart.timeScale().getVisibleRange()') == historical
            assert len(requests) == before
            await page.evaluate('''() => {const n=DataCache.renderBars.length;
                Canvas.chart.timeScale().setVisibleLogicalRange({from:n-1000,to:n-1});}''')
            await settle(page)
            await page.evaluate('DataCache.refreshStored()')
            await settle(page)
            assert await page.evaluate('liveSeries.data().at(-1).close') == 132
            print('PASS: history browsing pauses live requests and returning to newest resumes ticks',flush=True)

            # A new forming interval must not jump over a missing audited close.
            state['bar']=quote(T+STEP,133)
            await page.evaluate('DataCache.refreshStored()')
            await settle(page)
            assert await page.evaluate('DataCache.formingBar.time') == T//1000
            assert await page.evaluate('DataCache.liveStatus') == 'waiting for stored bar'
            db.write_klines([quote(T,132)['client']])
            db.write_features([dict(symbol='BTCUSDT',interval='15m',open_time=T,ema50=129)])
            await page.evaluate('DataCache.refreshStored()')
            await settle(page)
            assert await page.evaluate('DataCache.formingBar.time') == (T+STEP)//1000
            assert await page.evaluate('(t)=>DataCache.renderBars.filter(b=>b.open_time === t).length',T) == 1
            assert await page.evaluate('(t)=>DataCache.bars.find(b=>b.open_time === t).features.ema50',T) == 129
            assert await page.evaluate('(t)=>DataCache.bars.find(b=>b.open_time === t).provisional',T) is None
            assert db.count_klines('BTCUSDT','15m') == count+1
            print('PASS: rollover waits for stored closure, replaces provisional bar once, then follows the next live candle',flush=True)

            state.update(bar=None,status='unavailable',error='test upstream unavailable')
            await page.evaluate('DataCache.refreshStored()')
            await settle(page)
            assert await page.evaluate('DataCache.liveStatus') == 'unavailable'
            assert 'unavailable' in await page.locator('#status').text_content()
            assert not errors,errors
            assert not [u for u in requests if 'binance.com' in u or '/api/live_candle' in u]
            assert any('/api/bars?' in u and 'live=1' in u for u in requests)
            print('PASS: failed live source is visible without removing history or making direct exchange requests',flush=True)
            await browser.close()


if __name__=='__main__':
    run(Path(sys.argv[1]).resolve(),scenario=exercise_live)
