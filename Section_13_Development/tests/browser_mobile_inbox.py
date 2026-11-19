"""Mobile history is paged, cached offline and never links to a chart."""
import json
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from browser_smoke import run
from Section_11_UI_UX.server import alerts

async def exercise(base,library):
    conn=alerts.open_db()
    with conn:
        for i in range(125):
            event=dict(name='BUY',symbol='BTCUSDT',interval='15m',created=1790000000000+i,bar_time=i,details={'side':'BUY','price':100+i,'confidence':82,'upper':{'low':230,'high':240},'lower':{'low':80,'high':90}})
            conn.execute('INSERT INTO events(owner,rule_id,epoch,bar_time,created,packet) VALUES (?,?,?,?,?,?)',('admin','mobile'+str(i),'0',i,event['created'],json.dumps(event)))
    conn.close()
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        context=await browser.new_context();page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(base+'/web_root/mobile.html');await page.get_by_label('Username',exact=True).fill('admin');await page.get_by_label('Password',exact=True).fill('test-password-long');await page.get_by_role('button',name='Sign in',exact=True).click()
        await page.wait_for_function("document.querySelectorAll('#mobile-events .alert-toast').length===50")
        assert await page.locator('#mobile-events a').count()==0
        assert 'BTCUSDT' in await page.locator('#mobile-events').inner_text()
        await page.get_by_role('button',name='Older history',exact=True).click()
        await page.wait_for_function("document.getElementById('mobile-events').textContent.includes('Price 174')")
        await page.get_by_role('button',name='Older history',exact=True).click()
        await page.wait_for_function("document.querySelectorAll('#mobile-events .alert-toast').length===25")
        await page.get_by_label('Sound',exact=True).uncheck()
        await page.wait_for_function("InboxStore.settings(location.origin,'admin').then(p=>p.sound===false)")
        await context.set_offline(True);await page.reload();await page.wait_for_function("document.querySelectorAll('#mobile-events .alert-toast').length===50")
        assert not await page.get_by_label('Sound',exact=True).is_checked()
        assert not errors,errors
        await browser.close();print('PASS: 125 messages paged; no chart links; offline cached inbox; sound preference saved')

if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
