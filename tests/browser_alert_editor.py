"""Saved-alert manager and repeated independent editor operations under runner load."""
from pathlib import Path
import sys
import tempfile
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
            await page.get_by_role('button',name='Alerts',exact=True).click()
            manager=page.get_by_role('dialog',name='Alerts',exact=True)
            await manager.get_by_role('button',name='New alert',exact=True).wait_for()
            assert await manager.locator('form').count()==0
            for name in ['First alert','Second alert','Third alert']:
                await manager.get_by_role('button',name='New alert',exact=True).click()
                editor=page.get_by_role('dialog',name='Create alert',exact=True)
                await editor.get_by_label('Alert name',exact=True).fill(name)
                await editor.get_by_role('button',name='Create alert',exact=True).click()
                await editor.wait_for(state='hidden')
                await manager.locator('.alert-rule').get_by_text(name,exact=True).wait_for()
            rows=alerts.list_rules('user');assert len(rows)==3
            first=next(rule for rule in rows if rule['name']=='First alert')['id']
            row=manager.locator('.alert-rule').filter(has_text='First alert')
            await row.get_by_role('button',name='Edit',exact=True).click()
            editor=page.get_by_role('dialog',name='Edit alert',exact=True)
            await editor.get_by_label('Alert name',exact=True).fill('First edited')
            await editor.get_by_role('button',name='Save changes',exact=True).click()
            await editor.wait_for(state='hidden')
            await manager.locator('.alert-rule').get_by_text('First edited',exact=True).wait_for()
            assert len(alerts.list_rules('user'))==3
            assert next(rule for rule in alerts.list_rules('user') if rule['name']=='First edited')['id']==first
            await manager.locator('.alert-rule').filter(has_text='Second alert').get_by_role('button',name='Delete rule',exact=True).click()
            await manager.locator('.alert-rule').filter(has_text='Second alert').wait_for(state='hidden')
            await manager.get_by_role('button',name='New alert',exact=True).click()
            editor=page.get_by_role('dialog',name='Create alert',exact=True)
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
            await editor.wait_for(state='hidden')
            await manager.locator('.alert-rule').get_by_text('Retry alert',exact=True).wait_for()
            assert len(alerts.list_rules('user'))==3
            assert not errors,errors
            print('PASS: separate saved list and + editor; three consecutive alerts during runner lock and indefinitely suspended audio; edit preserves ID; delete; failed save can retry',flush=True)
            await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
