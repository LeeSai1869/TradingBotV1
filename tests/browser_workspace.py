"""Real-chart comparison workspace and persistent HUD configuration regression."""
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from browser_smoke import run, settle, sign_in


async def exercise(base,library):
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1600,'height':1000})
        errors=[];requests=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:requests.append(request.url))
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('window.DataCache && DataCache.bars.length===2000 && !DataCache._olderPromise')
        await settle(page)
        width=await page.locator('#chart').evaluate('(node)=>node.clientWidth')
        toggle=page.get_by_role('button',name='Analysis',exact=True)
        hud=page.locator('#chart-hud')
        await hud.get_by_role('table',name='BTCUSDT multi-timeframe comparison').wait_for()
        assert await page.locator('#analysis-panel').is_hidden()
        assert await page.locator('#chart').evaluate('(node)=>node.clientWidth')==width
        await toggle.click()
        panel=page.get_by_role('complementary',name='Analysis workspace')
        await hud.get_by_role('table',name='BTCUSDT multi-timeframe comparison').wait_for()
        await settle(page)
        assert await page.locator('#chart').evaluate('(node)=>node.clientWidth')<width
        assert await panel.get_by_role('heading',name='Best opportunity').is_visible()
        assert await panel.get_by_role('textbox',name='AI chat message').is_disabled()
        assert 'Stale' in await hud.locator('#comparison-hud').inner_text()
        await page.locator('#symbol').select_option('SUIUSDT')
        await hud.get_by_role('table',name='SUIUSDT multi-timeframe comparison').wait_for()
        await hud.get_by_role('button',name='Configure HUD',exact=True).click()
        settings=page.get_by_role('dialog',name='Settings',exact=True)
        await settings.get_by_label('HUD chart position',exact=True).select_option('bottom-right')
        await settings.get_by_label('HUD reference coin',exact=True).select_option('BTCUSDT')
        await settings.get_by_label('HUD timeframe 1m',exact=True).check()
        for interval in ['5m','15m','1h','4h']:
            await settings.get_by_label(f'HUD timeframe {interval}',exact=True).uncheck()
        assert await settings.get_by_label('HUD timeframe 1m',exact=True).is_disabled()
        await settings.get_by_label('HUD feature to add',exact=True).select_option('features.di_direction')
        await settings.get_by_role('button',name='Add feature row',exact=True).click()
        await settings.get_by_role('button',name='Apply',exact=True).click()
        await hud.get_by_role('table',name='BTCUSDT multi-timeframe comparison').wait_for()
        assert await hud.locator('thead th').count()==2
        assert await hud.get_by_role('rowheader',name='DI DIRECTION',exact=True).is_visible()
        assert await hud.locator('tbody tr').filter(has_text='EMA50').locator('td').inner_text()!='—'
        assert await page.locator('#symbol').input_value()=='SUIUSDT'
        # Only the body scrolls: Best opportunity remains pinned inside the panel.
        await panel.locator('.workspace-chat').evaluate("node=>{node.style.minHeight='1400px';}")
        opportunity=panel.get_by_role('heading',name='Best opportunity')
        top=(await opportunity.bounding_box())['y']
        await panel.locator('.workspace-body').evaluate('node=>{node.scrollTop=600;}')
        assert (await opportunity.bounding_box())['y']==top
        assert await panel.locator('.workspace-body').evaluate('node=>node.scrollTop')>0
        await panel.get_by_role('button',name='Collapse panel',exact=True).click()
        await settle(page)
        assert await page.locator('#chart').evaluate('(node)=>node.clientWidth')==width
        assert await hud.is_visible()
        assert await hud.get_attribute('data-position')=='bottom-right'
        assert await hud.evaluate("node=>getComputedStyle(node).backgroundColor")=='rgba(0, 0, 0, 0)'
        hud_toggle=page.get_by_role('button',name='Show comparison HUD',exact=True)
        await hud_toggle.click()
        assert await hud.is_hidden()
        before=len([url for url in requests if '/api/hud?' in url])
        await page.wait_for_timeout(5200)
        assert len([url for url in requests if '/api/hud?' in url])==before
        await page.reload();await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted')
        assert await hud.is_hidden()
        await hud_toggle.click()
        await hud.get_by_role('table',name='BTCUSDT multi-timeframe comparison').wait_for()
        assert await hud.locator('thead th').count()==2
        await page.set_viewport_size({'width':650,'height':850});await settle(page)
        await toggle.click()
        assert await panel.is_visible()
        assert await page.locator('#chart').evaluate('(node)=>node.clientWidth')==650
        assert not errors,errors
        assert not any('binance.com' in url for url in requests)
        print('PASS: transparent chart HUD independent of panel, persistent corner and visibility; pinned opportunity and scrollable chat;  collapsible panel resizes chart; HUD follows or pins coin; editable rows/timeframes persist; normal-user access; stale timestamps; hidden HUD stops requests; mobile drawer',flush=True)
        await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
