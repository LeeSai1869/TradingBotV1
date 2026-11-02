"""Automatic decision notification while a different chart is open."""
from pathlib import Path
import sys
import time
from unittest.mock import patch
from playwright.async_api import async_playwright
from browser_smoke import run, sign_in
from Section_11_UI_UX.server import alerts
from Section_1_Global_Core.memory_storage.Storage import db

async def exercise(base,library):
    with patch.object(alerts.data_policy,'active_symbols',return_value=['BTCUSDT','SUIUSDT']),patch.object(alerts.data_policy,'active_intervals',return_value=['1m']):
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=await browser.new_page(viewport={'width':1500,'height':1000})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            await page.add_init_script('''
                window.soundEvents=0;window.noticeEvents=[];
                window.AudioContext=class {constructor(){this.state='suspended';this.currentTime=0;this.destination={};} async resume(){this.state='running';}
                    createOscillator(){return {frequency:{value:0},connect(){},start(){soundEvents++;},stop(){}};}
                    createGain(){return {gain:{setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){}};}}
                window.Notification=class {static permission='default';static async requestPermission(){this.permission='granted';return 'granted';} constructor(name,options){noticeEvents.push({name,...options});}};
            ''')
            await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
            await page.goto(base);await sign_in(page,'user')
            await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000')
            await page.get_by_role('button',name='Enable sound / notifications',exact=True).click()
            await page.get_by_role('button',name='Sound on',exact=True).wait_for()
            alerts.sync_signal_rules()
            before=await page.evaluate('soundEvents')
            t=int(time.time()*1000)//60000*60000
            db.write_klines([dict(symbol='SUIUSDT',interval='1m',open_time=t,close_time=t+59999,open=10,high=12,low=9,close=11,volume=5)])
            with patch.object(alerts.time,'time',return_value=t/1000+61):alerts.evaluate_once()
            assert not alerts.events('user',0)['events']
            db.write_adcn([dict(symbol='SUIUSDT',interval='1m',open_time=t,signal_type='BUY',trigger='DI_TURNING_POINT_V3')])
            with patch.object(alerts.time,'time',return_value=t/1000+61):alerts.evaluate_once();alerts.evaluate_once()
            await page.locator('.alert-toast').filter(has_text='SUIUSDT 1m BUY').wait_for()
            assert await page.evaluate('soundEvents')>before
            assert await page.evaluate("noticeEvents.filter(e=>e.name==='BUY').length")==1
            assert await page.evaluate('DataCache.symbol')=='BTCUSDT'
            await page.get_by_role('button',name='Alerts',exact=True).click()
            manager=page.get_by_role('dialog',name='Alerts',exact=True)
            await manager.get_by_role('button',name='New alert',exact=True).click()
            editor=page.get_by_role('dialog',name='Create alert',exact=True)
            await editor.get_by_role('button',name='SELL signal',exact=True).click()
            assert await editor.get_by_label('Field',exact=True).input_value()=='decision.sell'
            assert not await editor.get_by_label('Threshold (signed numbers allowed)',exact=True).is_visible()
            await editor.get_by_label('Search fields',exact=True).fill('rsi')
            await editor.get_by_label('Field',exact=True).select_option('features.rsi')
            assert await editor.get_by_label('Threshold (signed numbers allowed)',exact=True).is_visible()
            await editor.get_by_role('button',name='Cancel',exact=True).click()
            await manager.get_by_role('button',name='Close alerts',exact=True).click()
            await page.get_by_role('button',name='Open settings',exact=True).click()
            settings=page.get_by_role('dialog',name='Settings',exact=True)
            await settings.get_by_role('tab',name='Features',exact=True).click()
            await settings.get_by_role('button',name='Momentum Indicator',exact=True).click()
            await page.wait_for_function("!document.querySelector('[aria-label=\"BUY sound\"]').disabled")
            await settings.get_by_label('BUY sound',exact=True).select_option('alarm')
            await settings.get_by_role('button',name='Apply',exact=True).click()
            await settings.wait_for(state='hidden')
            assert alerts.signal_preferences('user')['buy']=='alarm'
            assert not errors,errors
            await browser.close()
            print('PASS: unviewed canonical BUY, one sound/notification, waiting for decision, searchable editor and simple SELL preset')

if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
