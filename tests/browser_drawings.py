"""Compact icon tools, style/lock/timeframe editing and account memory across browsers."""
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in,settle

async def exercise(base,library):
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        context=await browser.new_context(viewport={'width':1800,'height':1200})
        page=await context.new_page();errors=[]
        await page.add_init_script('AbortSignal.timeout=undefined')
        page.on('pageerror',lambda e:errors.append(str(e)))
        await context.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000 && !DataCache._olderPromise')
        await page.get_by_role('button',name='Trend line',exact=True).wait_for(state='visible')
        await page.wait_for_function("!document.querySelector('[aria-label=\"Trend line\"]').disabled")
        await settle(page)
        chart=await page.locator('#chart').bounding_box();tools=await page.locator('.drawing-tools').bounding_box()
        assert tools['y']<chart['y']
        assert not await page.locator('#candle-details strong').count()
        overlay=page.locator('#drawing-overlay')
        async def click(x,y):await page.mouse.click(chart['x']+x,chart['y']+y)
        failed=[False]
        async def transient_failure(route):
            if route.request.method=='POST' and not failed[0]:
                failed[0]=True
                await route.fulfill(status=503,json={'error':'Temporary drawing storage failure'})
            else:await route.continue_()
        await page.route('**/api/drawings',transient_failure)
        for kind,points in [('Trend line',[(250,200),(550,300)]),('Rectangle zone',[(650,350),(850,450)]),('Horizontal line',[(400,550)]),('Fib retracement',[(1000,200),(1200,500)]),('Fib extension',[(250,350),(450,200),(600,400)])]:
            await page.get_by_role('button',name=kind,exact=True).click()
            for x,y in points:await click(x,y)
            await settle(page)
            if kind=='Trend line':
                notice=page.locator('.drawing-notice')
                await notice.wait_for(state='visible')
                assert 'unsaved' in await notice.inner_text()
                assert (await page.evaluate("fetch('/api/drawings?symbol=BTCUSDT').then(r=>r.json())"))['drawings']==[]
                await page.get_by_role('button',name='Retry saving drawings',exact=True).click()
                await page.wait_for_function("document.querySelector('.drawing-notice').textContent==='Drawings saved to your account.'")
        assert await overlay.locator(':scope > g').count()==5
        await click(490,280);await settle(page)
        popup=page.get_by_role('dialog',name='Drawing style')
        await popup.wait_for()
        await popup.get_by_label('Drawing color',exact=True).fill('#ff1234')
        await popup.get_by_label('Drawing width',exact=True).select_option('4')
        await popup.get_by_label('Drawing line style',exact=True).select_option('dashed')
        await popup.get_by_label('Lock position',exact=True).check()
        await popup.get_by_label('All timeframes',exact=True).check()
        await popup.get_by_role('button',name='Apply drawing',exact=True).click();await settle(page)
        await page.wait_for_function("document.querySelector('.drawing-notice').textContent==='Drawings saved to your account.'")
        data=await page.evaluate("fetch('/api/drawings?symbol=BTCUSDT').then(r=>r.json())")
        assert len(data['drawings'])==5
        assert data['drawings'][0]['locked'] is True
        assert data['drawings'][0]['style']['color']=='#ff1234'
        assert data['drawings'][0]['timeframes']==[]
        assert await overlay.locator('g[data-drawing="0"] line').first.get_attribute('stroke')=='#ff1234'
        assert not await overlay.locator('g[data-drawing="0"] circle').count()
        assert await page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('tradingbot.drawings.')).length")==0
        # A clean browser has no shared localStorage or cookies; the account retrieves its memory.
        other=await browser.new_context(viewport={'width':1800,'height':1200})
        await other.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        second=await other.new_page();second.on('pageerror',lambda e:errors.append(str(e)))
        await second.goto(base);await sign_in(second,'user')
        await second.wait_for_function("document.querySelectorAll('#drawing-overlay > g').length===5")
        await second.locator('#interval').select_option('1m')
        await second.wait_for_function("DataCache.timeframe==='1m' && !DataCache.loading && DataCache.bars.length>0")
        await settle(second)
        assert await second.locator('#drawing-overlay > g').count()==1
        # Another account cannot retrieve these drawings.
        admin=await browser.new_context();await admin.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        third=await admin.new_page();await third.goto(base);await sign_in(third,'admin')
        assert (await third.evaluate("fetch('/api/drawings?symbol=BTCUSDT').then(r=>r.json())"))['drawings']==[]
        await page.screenshot(path='/tmp/tradingbot-account-drawings.png')
        assert not errors,errors
        print('PASS: compact icons; popup color/width/pattern/lock/timeframes; account storage across clean browsers; cross-timeframe projection and account isolation',flush=True)
        await browser.close()

if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
