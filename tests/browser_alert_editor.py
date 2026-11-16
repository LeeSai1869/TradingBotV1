"""Saved-alert manager and repeated independent editor operations under runner load."""
from pathlib import Path
import sys
import tempfile
import json
import time
from unittest.mock import patch
from playwright.async_api import async_playwright
from browser_smoke import run, sign_in
from Section_1_Global_Core import data_policy
from Section_11_UI_UX.server import alerts


async def exercise(base,library):
    with tempfile.TemporaryDirectory() as directory,patch.object(data_policy,'LOCK_FILE',Path(directory)/'lock'),data_policy.locked():
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=await browser.new_page(viewport={'width':1500,'height':1000})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            await page.add_init_script("window.AudioContext=class {constructor(){this.state='suspended';} resume(){return new Promise(()=>{});}};")
            await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
            await page.goto(base);await sign_in(page,'user')
            await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000')
            before=alerts.signal_preferences('user')
            await page.get_by_role('button',name='Alerts',exact=True).click()
            editor=page.get_by_role('dialog',name='Alerts',exact=True)
            await editor.wait_for()
            assert await editor.get_by_role('tab').all_text_contents()==['Create Alert','Edit Alerts','Recent Alert History']
            for name in ['First alert','Second alert','Third alert']:
                await editor.get_by_role('tab',name='Create Alert',exact=True).click()
                if name=='First alert':
                    await editor.get_by_label('Coin',exact=True).select_option('ALL')
                    await editor.get_by_label('Timeframe',exact=True).select_option('ALL')
                await editor.get_by_label('Alert name',exact=True).fill(name)
                await editor.get_by_role('button',name='Create alert',exact=True).click()
                await editor.locator('#alert-panel-edit .notification-rule').get_by_text(name,exact=True).wait_for()
                assert await editor.is_visible()
                assert await editor.get_by_role('tab',name='Edit Alerts',exact=True).get_attribute('aria-selected')=='true'
                assert 'Alert saved.' not in await page.locator('body').inner_text()
            rows=alerts.list_rules('user');assert len(rows)==3
            assert alerts.signal_preferences('user')==before
            first=next(rule for rule in rows if rule['name']=='First alert')['id']
            assert next(rule for rule in rows if rule['id']==first)['symbol']=='ALL'
            row=editor.locator('.notification-rule').filter(has_text='First alert')
            await row.get_by_role('button',name='Edit First alert',exact=True).click()
            assert await editor.get_by_label('Coin',exact=True).input_value()=='ALL'
            assert await editor.get_by_label('Timeframe',exact=True).input_value()=='ALL'
            await editor.get_by_label('Alert name',exact=True).fill('First edited')
            await editor.get_by_label('Timeframe',exact=True).select_option('1m')
            await editor.get_by_role('button',name='Save changes',exact=True).click()
            await editor.locator('.notification-rule').get_by_text('First edited',exact=True).wait_for()
            assert len(alerts.list_rules('user'))==3
            assert next(rule for rule in alerts.list_rules('user') if rule['name']=='First edited')['id']==first
            assert next(rule for rule in alerts.list_rules('user') if rule['id']==first)['interval']=='1m'
            await editor.locator('.notification-rule').filter(has_text='Second alert').get_by_role('button',name='Remove Second alert',exact=True).click()
            await editor.locator('.notification-rule').filter(has_text='Second alert').wait_for(state='hidden')
            await editor.get_by_role('tab',name='Create Alert',exact=True).click()
            await editor.get_by_label('Alert name',exact=True).fill('Retry alert')
            async def fail(route):
                if route.request.method=='POST':await route.fulfill(status=503,content_type='application/json',body='{"error":"Temporary save failure"}')
                else:await route.continue_()
            await page.route('**/api/alerts',fail)
            await editor.get_by_role('button',name='Create alert',exact=True).click()
            await editor.get_by_role('status').filter(has_text='Temporary save failure').wait_for()
            assert await editor.get_by_role('button',name='Create alert',exact=True).is_enabled()
            await page.unroute('**/api/alerts',fail)
            await editor.get_by_role('button',name='Create alert',exact=True).click()
            await editor.locator('.notification-rule').get_by_text('Retry alert',exact=True).wait_for()
            assert len(alerts.list_rules('user'))==3

            # History reads the durable account store, including more than one page.
            await page.evaluate("dispatchEvent(new Event('pagehide'))")
            now=int(time.time()*1000)
            conn=alerts.open_db()
            try:
                with conn:
                    for index in range(127):
                        owner='admin' if index==126 else 'user'
                        created=now-90_000_000 if index==125 else now-1000-index
                        event=dict(name='PRIVATE' if owner=='admin' else f'History {index:03}',symbol='BTCUSDT',interval='1m',created=created,bar_time=1781653500000,message='Stored alert history',sound='none',notify=False)
                        conn.execute('INSERT INTO events(owner,rule_id,epoch,bar_time,created,packet) VALUES (?,?,?,?,?,?)',(owner,'history','0',index,created,json.dumps(event)))
                    automatic=dict(name='Automatic BUY decision',symbol='BTCUSDT',interval='1m',created=now,bar_time=1781653500000,message='Automatic decision',field='decision.buy',notify=True)
                    conn.execute('INSERT INTO events(owner,rule_id,epoch,bar_time,created,packet) VALUES (?,?,?,?,?,?)',('user','auto:signal','0',999,now,json.dumps(automatic)))
            finally:conn.close()
            await editor.get_by_role('tab',name='Recent Alert History',exact=True).click()
            history=editor.get_by_role('tabpanel',name='Recent Alert History',exact=True)
            await page.wait_for_function("document.querySelectorAll('#alert-panel-history .alert-rule').length===100")
            await history.get_by_role('button',name='Load more alerts',exact=True).click()
            await page.wait_for_function("document.querySelectorAll('#alert-panel-history .alert-rule').length===125")
            assert not await history.get_by_role('button',name='Load more alerts',exact=True).is_visible()
            assert 'PRIVATE' not in await history.inner_text()
            assert 'Automatic BUY decision' not in await history.inner_text()
            assert 'History 125' not in await history.inner_text()
            await history.get_by_label('History period',exact=True).select_option('yesterday')
            await page.wait_for_function("!document.querySelector('#alert-panel-history button').disabled")
            await history.get_by_label('History period',exact=True).select_option('24h')
            await page.wait_for_function("document.querySelectorAll('#alert-panel-history .alert-rule').length===100")
            await editor.get_by_role('tab',name='Edit Alerts',exact=True).click()
            await editor.locator('.notification-rule').get_by_text('First edited',exact=True).wait_for()
            await page.screenshot(path='/private/tmp/scalp-alert-tabs.png')
            await editor.get_by_role('button',name='Close alert editor',exact=True).click()
            await page.get_by_role('button',name='Alerts',exact=True).click()
            assert await editor.get_by_role('tab',name='Create Alert',exact=True).get_attribute('aria-selected')=='true'
            assert not errors,errors
            print('PASS: three alert tabs, ALL scopes, named edit/delete, silent save, retry, full-day paginated private history and unchanged delivery preferences',flush=True)
            await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
