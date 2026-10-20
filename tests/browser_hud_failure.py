"""HUD network failures must not prevent the chart or settings recovery."""
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from browser_smoke import run, sign_in


async def exercise(base,library):
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1600,'height':1000})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        async def unavailable(route):
            await route.fulfill(status=503,content_type='application/json',body='{"error":"Market data is busy. Retry shortly."}')
        await page.route('**/api/hud?*',unavailable)
        await page.route('**/api/hud/catalog',lambda route:route.abort())
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('window.DataCache && DataCache.bars.length===2000 && !DataCache._olderPromise')
        assert 'busy' in await page.locator('#chart-hud').inner_text()
        assert 'Error:' not in await page.locator('#status').inner_text()
        await page.get_by_role('button',name='Open settings',exact=True).click()
        settings=page.get_by_role('dialog',name='Settings',exact=True)
        await settings.get_by_role('tab',name='HUD',exact=True).click()
        await settings.get_by_role('button',name='Retry HUD settings',exact=True).wait_for()
        assert 'restart_ui.py' in await settings.inner_text()
        assert 'Loading HUD settings' not in await settings.inner_text()
        await page.unroute('**/api/hud/catalog')
        await settings.get_by_role('button',name='Retry HUD settings',exact=True).click()
        await settings.get_by_label('HUD reference coin',exact=True).wait_for()
        await page.unroute('**/api/hud?*')
        await settings.get_by_role('button',name='Apply',exact=True).click()
        await page.get_by_role('table',name='BTCUSDT multi-timeframe comparison').wait_for()
        assert await page.evaluate('DataCache.bars.length')==2000
        assert not errors,errors
        print('PASS: busy HUD and failed catalog do not stop chart; settings exit Loading with retry; catalog and overlay recover without app restart',flush=True)
        await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
