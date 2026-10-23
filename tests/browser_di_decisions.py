"""A real stored DI decision reaches the candle marker through the combined API."""
from pathlib import Path
import sys
from unittest.mock import patch
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in,settle,db,features_store
from Section_8_Decision_Engine import processor


async def exercise(base,library):
    rows=db.read_last_klines('BTCUSDT','15m',3)
    values=[(10,30),(11,35),(15,27)]
    db.write_features([dict(symbol='BTCUSDT',interval='15m',open_time=r[2],formula_version=3,
                            di_plus=plus,di_minus=minus,di_spread=abs(plus-minus),adx=20+i,ema50=r[6])
                       for i,(r,(plus,minus)) in enumerate(zip(rows,values))])
    db.write_klines([dict(symbol='BTCUSDT',interval='15m',open_time=r[2],open=100+i,high=103+i,low=99+i,close=101+i,volume=5,close_time=r[8]) for i,r in enumerate(rows)])
    conn=features_store.open_db()
    conn.execute('INSERT OR REPLACE INTO feature_engine_state VALUES (?,?,?,?)',('BTCUSDT','15m',rows[-1][2],'{}'));conn.commit();conn.close()
    with patch.object(processor.data_policy,'enabled',return_value=True):
        assert processor.catch_up('BTCUSDT','15m')==1
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page();errors=[];requests=[]
        page.on('pageerror',lambda error:errors.append(str(error)));page.on('request',lambda request:requests.append(request.url))
        source=library.read_text()+'''
const originalMarkers=LightweightCharts.createSeriesMarkers;
LightweightCharts={...LightweightCharts,createSeriesMarkers:(series,markers,...args)=>{
 window.decisionMarkers=markers;
 const api=originalMarkers(series,markers,...args),set=api.setMarkers.bind(api);
 api.setMarkers=markers=>{window.decisionMarkers=markers;return set(markers);};return api;
}};
'''
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(body=source,content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && !DataCache.loading && !DataCache._olderPromise')
        await settle(page)
        assert await page.evaluate('DataCache.latestBar.adcn.signal_type')=='BUY'
        assert await page.evaluate('DataCache.latestBar.adcn.final_score') is None
        marker=await page.evaluate('(time)=>window.decisionMarkers.find(x=>x.time===time)',rows[-1][2]//1000)
        assert marker['text']=='B' and marker['position']=='belowBar',marker
        assert not any('/api/decisions' in url for url in requests)
        assert not errors,errors
        print('PASS: closed DI rule writes ADCN and renders BUY on the same canonical candle without an invented score or separate decision request',flush=True)
        await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
