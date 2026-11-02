"""Top-level settings, own-audio round trip and independent notification scopes."""
import io
from pathlib import Path
import sys
import wave
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in
from Section_11_UI_UX.server import alerts

async def exercise(base,library):
    raw=io.BytesIO()
    with wave.open(raw,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(8000);audio.writeframes(b'\0\0'*800)
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1600,'height':1000});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        await page.add_init_script("window.customPlays=0;const create=AudioContext.prototype.createBufferSource;AudioContext.prototype.createBufferSource=function(){customPlays++;return create.call(this);};")
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'admin');await page.wait_for_function('Composer?.mounted')
        toggle=page.get_by_role('button',name='Toggle desktop notifications',exact=True)
        await toggle.wait_for();await page.wait_for_function("!document.getElementById('alerts-button').disabled")
        before=alerts.signal_preferences('admin')['notify'];await toggle.click()
        await page.wait_for_function("!document.getElementById('alerts-button').disabled")
        assert alerts.signal_preferences('admin')['notify'] is not before
        assert not await page.get_by_role('dialog',name='Settings',exact=True).is_visible()
        await page.get_by_role('button',name='Open settings',exact=True).click();settings=page.get_by_role('dialog',name='Settings',exact=True)
        await settings.get_by_role('tab',name='Features',exact=True).click()
        assert await settings.get_by_role('button',name='Sounds',exact=True).count()==0
        assert await settings.get_by_role('button',name='Notifications',exact=True).count()==0
        await settings.get_by_role('tab',name='Sounds',exact=True).click()
        await settings.get_by_label('Choose audio file',exact=True).set_input_files({'name':'My tone.wav','mimeType':'audio/wav','buffer':raw.getvalue()})
        await settings.get_by_role('button',name='Preview new sound',exact=True).click()
        assert await page.evaluate('customPlays')==1
        await settings.get_by_role('button',name='Add sound',exact=True).click()
        await settings.get_by_role('button',name='Delete My tone',exact=True).wait_for()
        key=alerts.sounds('admin')['sounds'][0]['id']
        await settings.get_by_label('BUY sound',exact=True).select_option(key)
        await page.wait_for_function("key=>fetch('/api/alerts/signals').then(r=>r.json()).then(p=>p.buy===key)",arg=key)
        await settings.get_by_role('button',name='Preview BUY sound',exact=True).click()
        await page.wait_for_function('customPlays===2')
        await settings.get_by_role('tab',name='Timeframes',exact=True).click()
        await settings.get_by_label('5m Desktop notifications',exact=True).uncheck()
        assert await settings.get_by_label('5m Mobile notifications',exact=True).is_disabled()
        assert await settings.get_by_label('5m download status',exact=True).input_value()=='active'
        assert await settings.get_by_label('5m Sound alerts',exact=True).count()==0
        await settings.get_by_role('tab',name='Coins',exact=True).click()
        await settings.get_by_label('BTCUSDT Desktop notifications',exact=True).uncheck()
        assert await settings.get_by_label('BTCUSDT Mobile notifications',exact=True).is_disabled()
        await page.wait_for_function("fetch('/api/alerts/signals').then(r=>r.json()).then(p=>p.coins.BTCUSDT.desktop===false&&p.timeframes['5m'].desktop===false)")
        assert alerts.signal_preferences('admin')['buy']==key
        await settings.get_by_role('tab',name='Sounds',exact=True).click()
        await settings.get_by_role('button',name='Delete My tone',exact=True).click()
        await page.wait_for_function("fetch('/api/alerts/signals').then(r=>r.json()).then(p=>p.buy==='none')")
        assert alerts.sounds('admin')['sounds']==[]
        assert not errors,errors
        await browser.close()
        print('PASS: top-level menus; toolbar toggle; upload/preview/assign/delete real WAV; per-timeframe/per-coin Desktop switches; Mobile deferred; sound unchanged by notification scopes')

if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
