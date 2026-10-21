"""Manual chart drawings, compact header/footer and bulk feature selections."""
from pathlib import Path
import sys
import re
from playwright.async_api import async_playwright
from browser_smoke import run, sign_in, settle


async def exercise(base,library):
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1800,'height':1200})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda message:errors.append(message.text) if message.type=='error' else None)
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000 && !DataCache._olderPromise')
        await settle(page)
        assert not await page.locator('#flags-panel').count()
        assert await page.locator('#candle-details dt').all_text_contents()==['O','H','L','C','Vol','Δ%']
        chart=await page.locator('#chart').bounding_box();footer=await page.locator('#status').bounding_box()
        assert footer['y']>=chart['y']+chart['height']-1
        tool=page.get_by_role('combobox',name='Drawing tool',exact=True)
        overlay=page.locator('#drawing-overlay')
        async def click(x,y):await page.mouse.click(chart['x']+x,chart['y']+y)
        for kind,points in [('line',[(250,200),(550,300)]),('rectangle',[(650,350),(850,450)]),
                            ('horizontal',[(400,550)]),('retracement',[(1000,200),(1200,500)]),
                            ('extension',[(250,350),(450,200),(600,400)])]:
            await tool.select_option(kind)
            for x,y in points:await click(x,y)
            await settle(page)
            assert await tool.input_value()=='pointer'
        assert await overlay.locator(':scope > g[data-drawing]').count()==5
        assert await overlay.locator('text').filter(has_text=re.compile(r'^61\.80%')).count()==2
        horizontal=overlay.locator('g[data-type=horizontal] line').first
        assert float(await horizontal.get_attribute('x1'))==0
        assert float(await horizontal.get_attribute('x2'))>1500
        key=await page.evaluate("Object.keys(localStorage).find(key=>key.startsWith('tradingbot.drawings.v1.'))")
        saved=await page.evaluate('(key)=>JSON.parse(localStorage.getItem(key))',key)
        await click(490,280);await settle(page)
        handle=overlay.locator('g[data-drawing="0"] circle').first
        box=await handle.bounding_box()
        await page.mouse.move(box['x']+5,box['y']+5);await page.mouse.down()
        await page.mouse.move(box['x']+45,box['y']+25,steps=5);await page.mouse.up();await settle(page)
        changed=await page.evaluate('(key)=>JSON.parse(localStorage.getItem(key))',key)
        assert saved[0]['anchors']!=changed[0]['anchors']
        await page.get_by_role('button',name='Undo drawing',exact=True).click();await settle(page)
        assert saved==await page.evaluate('(key)=>JSON.parse(localStorage.getItem(key))',key)
        before=float(await overlay.locator('g[data-drawing="0"] line').first.get_attribute('x1'))
        await page.evaluate('''()=>{const r=Canvas.chart.timeScale().getVisibleLogicalRange();Canvas.chart.timeScale().setVisibleLogicalRange({from:r.from+20,to:r.to+20});}''')
        await settle(page)
        after=float(await overlay.locator('g[data-drawing="0"] line').first.get_attribute('x1'))
        assert abs(after-before)>50
        await tool.select_option('extension');await click(200,200);await page.keyboard.press('Escape');await settle(page)
        assert await overlay.locator(':scope > g[data-drawing]').count()==5
        await page.reload();await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000')
        await settle(page)
        assert await overlay.locator(':scope > g[data-drawing]').count()==5
        await page.get_by_role('button',name='Open settings',exact=True).click()
        settings=page.get_by_role('dialog',name='Settings',exact=True)
        await settings.get_by_role('tab',name='Features',exact=True).click()
        for feature in ['EMA','RSI','ADX','DI','ATR','Volume','VWAP']:
            await settings.get_by_role('button',name=feature,exact=True).click()
            await settings.get_by_role('button',name='Select all',exact=True).click()
            assert await settings.locator('.settings-style-table input[type=checkbox]:not(:checked)').count()==0
            await settings.get_by_role('button',name='Deselect all',exact=True).click()
            assert await settings.locator('.settings-style-table input[type=checkbox]:checked').count()==0
        await settings.get_by_role('button',name='Cancel',exact=True).click()
        await tool.select_option('horizontal');await click(300,700);await settle(page)
        assert await overlay.locator(':scope > g[data-drawing]').count()==6
        await page.get_by_role('button',name='Delete drawing',exact=True).click();await settle(page)
        assert await overlay.locator(':scope > g[data-drawing]').count()==5
        await page.get_by_role('button',name='Undo drawing',exact=True).click();await settle(page)
        assert await overlay.locator(':scope > g[data-drawing]').count()==6
        await page.get_by_role('button',name='Undo drawing',exact=True).click();await settle(page)
        assert await overlay.locator(':scope > g[data-drawing]').count()==5
        await page.locator('#interval').select_option('1m')
        await page.wait_for_function("DataCache.timeframe==='1m' && !DataCache.loading && DataCache.bars.length>0")
        await settle(page)
        assert await overlay.locator(':scope > g[data-drawing]').count()==0
        await page.locator('#interval').select_option('15m')
        await page.wait_for_function("DataCache.timeframe==='15m' && !DataCache.loading && DataCache.bars.length>0")
        await settle(page)
        assert await overlay.locator(':scope > g[data-drawing]').count()==5
        await page.screenshot(path='/tmp/tradingbot-drawings.png')
        assert not errors,errors
        print('PASS: compact candle strip/footer, no flags panel, all five drawing tools, drag/undo, time anchoring, cancellation, persistence and bulk feature selections',flush=True)
        await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
