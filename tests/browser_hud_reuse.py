"""A matching HUD column uses chart cache, including live ticks, without HUD data requests."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from playwright.async_api import async_playwright
from browser_smoke import run, sign_in, settle
from Section_1_Global_Core import data_policy


async def exercise(base,library):
    with tempfile.TemporaryDirectory() as directory,patch.object(data_policy,'LOCK_FILE',Path(directory)/'lock'),data_policy.locked():
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=await browser.new_page(viewport={'width':1600,'height':1000})
            requests=[];errors=[]
            page.on('request',lambda request:requests.append(request.url))
            page.on('pageerror',lambda error:errors.append(str(error)))
            await page.add_init_script("localStorage.setItem('tradingbot.chart-settings.v1',JSON.stringify({hud:{symbol:'',intervals:['15m'],fields:['client.close','features.ema50']}}));")
            await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
            await page.goto(base);await sign_in(page,'user')
            await page.wait_for_function('window.DataCache && DataCache.bars.length===2000 && !DataCache._olderPromise')
            table=page.get_by_role('table',name='BTCUSDT multi-timeframe comparison')
            await table.wait_for()
            assert not any('/api/hud?' in url for url in requests),requests
            await page.evaluate('''() => {
                const previous=DataCache.latestBar, t=previous.client.close_time+1;
                DataCache.formingBar={symbol:previous.symbol,interval:previous.interval,open_time:t,time:t/1000,provisional:true,
                    client:{...previous.client,open_time:t,close_time:t+900000-1,open:440,high:450,low:430,close:444},features:{ema50:444.5},adcn:null};
                DataCache.liveStatus='live';DataCache.emit('live');
            }''')
            await settle(page)
            assert await table.locator('tbody tr').filter(has_text='Close').locator('td').inner_text()=='444'
            assert await table.locator('tbody tr').filter(has_text='EMA50').locator('td').inner_text()=='444.5'
            assert 'Live' in await table.inner_text()
            await page.wait_for_timeout(5200)
            assert not any('/api/hud?' in url for url in requests),requests
            assert not errors,errors
            print('PASS: chart loads while runner writer lock is held; matching HUD reuses closed/live chart values with zero HUD data requests, including polling',flush=True)
            await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
