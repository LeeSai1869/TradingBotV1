"""Real browser/server role, policy and deletion flow; disposable stores only."""
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from playwright.async_api import async_playwright
from browser_smoke import run, settle, db
from Section_1_Global_Core import data_policy, data_admin
from Section_1_Global_Core.Symbols import symbols
from Section_11_UI_UX.server import auth, settings_catalog


async def exercise_admin(base, library):
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1500,'height':1000})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        await page.route('https://unpkg.com/**',lambda r:r.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base)
        await page.wait_for_function('window.DataCache && DataCache.bars.length===2000&&!DataCache._olderPromise')
        await settle(page)
        await page.get_by_role('button',name='Open settings').click()
        dialog=page.get_by_role('dialog',name='Settings')
        await dialog.get_by_role('tab',name='Timeframes',exact=True).click()
        assert await dialog.get_by_label('3m download status',exact=True).is_disabled()
        async def login(name):
            await dialog.get_by_role('tab',name='General',exact=True).click()
            await dialog.get_by_role('button',name='Account',exact=True).click()
            await dialog.get_by_label('Username',exact=True).fill(name)
            await dialog.get_by_label('Password',exact=True).fill('test-password-long')
            await dialog.get_by_role('button',name='Sign in',exact=True).click()
            await dialog.get_by_text(f'Signed in as {name} ({name}).',exact=True).wait_for()
        await login('user')
        await dialog.get_by_role('tab',name='Timeframes',exact=True).click()
        await dialog.get_by_label('3m download status',exact=True).select_option('inactive')
        await dialog.get_by_label('3m download status',exact=True).wait_for(state='visible')
        assert await dialog.get_by_role('button',name='Delete data',exact=True).first.is_disabled()
        denied=await page.request.post(base+'/api/settings/delete',data={'interval':'15m','confirmation':'DELETE 15m'})
        assert denied.status==403
        assert db.count_klines('BTCUSDT','15m')==14000
        await dialog.get_by_role('tab',name='General',exact=True).click()
        await dialog.get_by_role('button',name='Account',exact=True).click()
        await dialog.get_by_role('button',name='Sign out',exact=True).click()
        await login('admin')
        await dialog.get_by_role('tab',name='Timeframes',exact=True).click()
        section=dialog.locator('.settings-policy-item').filter(has=page.get_by_text('15m',exact=True))
        await section.get_by_role('button',name='Delete data',exact=True).click()
        confirmation=section.get_by_label('Type DELETE 15m',exact=True)
        await confirmation.fill('wrong')
        await section.get_by_role('button',name='Confirm deletion',exact=True).click()
        await section.get_by_text('Type DELETE 15m to confirm deletion',exact=True).wait_for()
        assert db.count_klines('BTCUSDT','15m')==14000
        await confirmation.fill('DELETE 15m')
        await section.get_by_role('button',name='Confirm deletion',exact=True).click()
        await page.wait_for_function('DataCache.bars.length===0&&!DataCache.loading')
        assert db.count_klines('BTCUSDT','15m')==0
        assert db.count_klines('BTCUSDT','1m')==2200
        await page.wait_for_function("document.querySelector('[aria-label=\"15m download status\"]').value==='inactive'")
        await dialog.get_by_label('15m download status',exact=True).select_option('active')
        await page.wait_for_function("!document.querySelector('[aria-label=\"15m download status\"]').disabled")
        assert data_policy.read()['timeframes']['15m']=='active'
        await dialog.get_by_role('tab',name='Coins',exact=True).click()
        await dialog.get_by_label('Select SUIUSDT',exact=True).check()
        await dialog.get_by_role('button',name='Disapprove',exact=True).click()
        await dialog.get_by_label('Select SUIUSDT',exact=True).wait_for(state='hidden')
        assert 'SUIUSDT' not in data_policy.active_symbols()
        assert db.count_klines('SUIUSDT','1m')==2200
        await dialog.get_by_role('button',name='Disapproved',exact=True).click()
        await dialog.get_by_label('Select SUIUSDT',exact=True).check()
        await dialog.get_by_role('button',name='Delete data',exact=True).click()
        await dialog.get_by_label('Type DELETE SUIUSDT',exact=True).fill('DELETE SUIUSDT')
        await dialog.get_by_role('button',name='Confirm deletion',exact=True).click()
        await dialog.get_by_label('Type DELETE SUIUSDT',exact=True).wait_for(state='hidden')
        assert db.count_klines('SUIUSDT','1m')==0
        assert 'SUIUSDT' in symbols.get_disapproved_symbols()
        await dialog.get_by_role('button',name='Approve / activate',exact=True).click()
        await dialog.get_by_label('Select SUIUSDT',exact=True).wait_for(state='hidden')
        assert 'SUIUSDT' in data_policy.active_symbols()
        await page.wait_for_function("[...document.querySelector('#symbol').options].some(o=>o.value==='SUIUSDT')")
        assert await page.locator('#symbol').input_value() == 'BTCUSDT'
        assert not errors,errors
        await browser.close()
        print('PASS: real login/user/admin sessions, normal-user deletion denied, immediate timeframe policy, typed deletion, chart cache cleared, scoped coin deletion and reapproval without removing registry entries')


if __name__=='__main__':
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        root=Path(directory)
        for module,attr,name in [(data_policy,'POLICY_FILE','policy.json'),(data_policy,'LOCK_FILE','lock'),
                (auth,'USERS_FILE','users.json'),(data_admin,'REGISTRY_FILE','symbols.json'),
                (symbols,'_SYMBOLS_JSON','symbols.json'),(settings_catalog,'REGISTRY_PATH','symbols.json')]:
            stack.enter_context(patch.object(module,attr,root/name))
        registry=dict(schema_version=2,active_cap=50,approved=[dict(symbol='BTCUSDT'),dict(symbol='SUIUSDT')],
                      top50=[dict(symbol='BTCUSDT'),dict(symbol='SUIUSDT')],pending=[],disapproved=[],staged=[])
        (root/'symbols.json').write_text(json.dumps(registry));symbols.reload()
        salt='12'*16
        auth.USERS_FILE.write_text(json.dumps({name:dict(role=name,salt=salt,hash=auth.digest('test-password-long',salt)) for name in ['admin','user']}))
        try: run(Path(sys.argv[1]).resolve(),scenario=exercise_admin)
        finally: symbols.reload()
