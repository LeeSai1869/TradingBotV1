"""Symbol dropdown: blank search above the entire scrollable symbol list."""
import json
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in,settle


async def exercise(base,library):
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1100,'height':800})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        symbols=['BTCUSDT','SUIUSDT','ETHUSDT']+[f'TEST{i:02}USDT' for i in range(60)]
        await page.route('**/api/symbols',lambda route:route.fulfill(body=json.dumps({'symbols':symbols}),content_type='application/json'))
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000 && !DataCache._olderPromise')
        trigger=page.get_by_role('button',name='Choose symbol',exact=True)
        search=page.get_by_role('combobox',name='Search symbol',exact=True)
        choices=page.get_by_role('listbox',name='Matching symbols')
        assert 'BTCUSDT' in await trigger.inner_text()
        await trigger.click()
        assert await search.input_value()==''
        assert 'BTCUSDT' not in await trigger.inner_text()
        assert await choices.get_by_role('option').count()==63
        assert await page.evaluate('document.activeElement.id')=='symbol-search'
        await search.fill('bitcoin')
        assert await choices.get_by_role('option').count()==1
        await search.press('Escape')
        assert await page.locator('#symbol-search-menu').is_hidden()
        assert await page.locator('#symbol').input_value()=='BTCUSDT'
        await trigger.click();assert await search.input_value()==''
        await search.fill('sui');await search.press('Enter')
        await page.wait_for_function('!DataCache.loading && DataCache.symbol==="SUIUSDT"')
        assert 'SUIUSDT' in await trigger.inner_text()
        await trigger.click();assert await search.input_value()==''
        assert await choices.get_by_role('option').count()==63
        await choices.evaluate('(el)=>{el.scrollTop=el.scrollHeight}')
        assert await search.is_visible()
        await search.fill('zz-no-match');assert await choices.inner_text()=='No matching symbols'
        await search.press('Escape');assert 'SUIUSDT' in await trigger.inner_text()
        await page.set_viewport_size({'width':360,'height':640});await trigger.click()
        box=await page.locator('#symbol-search-menu').bounding_box()
        assert box['x']>=0 and box['x']+box['width']<=360
        await page.mouse.click(20,500)
        assert await page.locator('#symbol-search-menu').is_hidden()
        assert not errors,errors
        print('PASS: full 63-symbol dropdown, blank focused search on every open, symbol/name filtering, selection, escape/outside dismissal, pinned search and narrow viewport',flush=True)
        await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
