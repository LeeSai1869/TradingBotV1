"""Live/stored alert delivery, editable fields/sounds, selection and remembered login."""
from pathlib import Path
import sys
import time
from unittest.mock import patch
from playwright.async_api import async_playwright
from browser_smoke import run, settle, sign_in, db, auth
from Section_11_UI_UX.server import alerts


async def exercise(base,library):
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1500,'height':1000})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        await page.add_init_script('''
            window.soundEvents=0;window.noticeEvents=[];
            window.AudioContext=class {
                constructor(){this.state='suspended';this.currentTime=0;this.destination={};}
                async resume(){this.state='running';}
                createOscillator(){return {frequency:{value:0},connect(){},start(){soundEvents++;},stop(){}};}
                createGain(){return {gain:{setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){}};}
            };
            window.Notification=class {
                static permission='default';
                static async requestPermission(){this.permission='granted';return 'granted';}
                constructor(name,options){noticeEvents.push({name,...options});}
            };
        ''')
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('DataCache.bars.length===2000&&!DataCache._olderPromise');await settle(page)
        await page.get_by_role('button',name='Alerts',exact=True).click()
        dialog=page.get_by_role('dialog',name='Alerts',exact=True)
        await dialog.get_by_role('button',name='Enable notifications and sound',exact=True).click()
        await dialog.get_by_role('button',name='New alert',exact=True).click()
        manager=dialog
        dialog=page.get_by_role('dialog',name='Create alert',exact=True)
        await dialog.get_by_label('Alert name',exact=True).fill('RSI crossing test')
        await dialog.get_by_label('Timeframe',exact=True).select_option('1m')
        await dialog.get_by_label('Field',exact=True).select_option('features.rsi')
        await dialog.get_by_label('Evaluation',exact=True).select_option('closed')
        await dialog.get_by_label('Condition',exact=True).select_option('above')
        await dialog.get_by_label('Threshold (signed numbers allowed)',exact=True).fill('70')
        await dialog.get_by_label('Sound',exact=True).select_option('bell')
        await dialog.get_by_role('button',name='Test selected sound',exact=True).click()
        await dialog.get_by_role('button',name='Create alert',exact=True).click()
        dialog=manager
        await dialog.locator('.alert-rule').get_by_text('RSI crossing test',exact=True).wait_for()
        await dialog.get_by_role('button',name='Close alerts',exact=True).click()
        before=await page.evaluate('soundEvents')
        await page.evaluate('Canvas.chart.timeScale().setVisibleLogicalRange({from:700,to:1699})');await settle(page)
        assert await page.evaluate('DataCache.timeframe')=='15m'
        t=int(time.time()*1000)//60000*60000
        raw=dict(symbol='BTCUSDT',interval='1m',open_time=t,close_time=t+59999,open=10,high=12,low=9,close=11,volume=5)
        db.write_klines([raw])
        with patch.object(alerts.time,'time',return_value=t/1000+61): alerts.evaluate_once()
        assert alerts.events('user',0)['events']==[]
        db.write_features([dict(symbol='BTCUSDT',interval='1m',open_time=t,rsi=75)])
        with patch.object(alerts.time,'time',return_value=t/1000+61): alerts.evaluate_once()
        await page.locator('.alert-toast').filter(has_text='RSI crossing test').wait_for()
        assert await page.evaluate('soundEvents')>before
        assert await page.evaluate("noticeEvents.some(e=>e.name==='RSI crossing test')")
        assert await page.evaluate('DataCache.atLiveEdge') is False
        await page.get_by_role('button',name='Alerts',exact=True).click()
        await dialog.get_by_role('button',name='New alert',exact=True).click()
        dialog=page.get_by_role('dialog',name='Create alert',exact=True)
        assert await dialog.get_by_label('Coin',exact=True).input_value()==await page.locator('#symbol').input_value()
        assert await dialog.get_by_label('Timeframe',exact=True).input_value()==await page.locator('#interval').input_value()
        await dialog.get_by_label('Alert name',exact=True).fill('Live SUI alert')
        await dialog.get_by_label('Coin',exact=True).select_option('SUIUSDT')
        await dialog.get_by_label('Timeframe',exact=True).select_option('1m')
        await dialog.get_by_label('Field',exact=True).select_option('client.close')
        await dialog.get_by_label('Evaluation',exact=True).select_option('live')
        await dialog.get_by_label('Condition',exact=True).select_option('crosses_above')
        await dialog.get_by_label('Threshold (signed numbers allowed)',exact=True).fill('10')
        await dialog.get_by_label('Sound',exact=True).select_option('alarm')
        await dialog.get_by_role('button',name='Create alert',exact=True).click()
        dialog=manager
        await dialog.locator('.alert-rule').get_by_text('Live SUI alert',exact=True).wait_for()
        await dialog.get_by_role('button',name='Close alerts',exact=True).click()
        bar=dict(symbol='SUIUSDT',interval='1m',open_time=t,time=t//1000,client=dict(close=9,high=9,low=8))
        with patch.object(alerts.live_candle,'get_snapshot',return_value={'bar':bar,'status':'live'}):
            alerts.evaluate_once();bar['client']['close']=11;alerts.evaluate_once();alerts.evaluate_once()
        await page.locator('.alert-toast').filter(has_text='Live SUI alert').wait_for()
        assert len(alerts.events('user',0)['events'])==2
        assert alerts.events('admin',0)['events']==[]
        await page.get_by_role('button',name='Open settings',exact=True).click()
        settings=page.get_by_role('dialog',name='Settings',exact=True)
        await settings.get_by_role('button',name='Account',exact=True).click()
        await settings.get_by_role('button',name='Sign out',exact=True).click()
        screen=page.locator('#login-screen')
        await screen.get_by_label('Remember me for 30 days',exact=True).check()
        await sign_in(page,'admin')
        await page.wait_for_function('DataCache.bars.length===2000&&!DataCache._olderPromise');await settle(page)
        auth.SESSIONS.clear()
        await page.reload()
        await page.wait_for_function('window.DataCache && DataCache.bars.length===2000&&!DataCache._olderPromise')
        assert await screen.is_hidden()
        assert 'Administrator' in await page.locator('#account-button').inner_text()
        await page.get_by_role('button',name='Open settings',exact=True).click()
        await settings.get_by_role('tab',name='Coins',exact=True).click()
        await settings.get_by_label('Select BTCUSDT',exact=True).wait_for()
        count=await settings.locator('.settings-coin input').count()
        await settings.get_by_role('button',name='Select all',exact=True).click()
        assert await settings.locator('.settings-coin input:checked').count()==count
        await settings.get_by_role('button',name='Deselect all',exact=True).click()
        assert await settings.locator('.settings-coin input:checked').count()==0
        await settings.get_by_role('tab',name='General',exact=True).click()
        await settings.get_by_role('button',name='Account',exact=True).click()
        await settings.get_by_role('button',name='Sign out',exact=True).click()
        await screen.get_by_label('Username',exact=True).wait_for()
        assert await page.locator('#app').is_hidden()
        assert not errors,errors
        await browser.close()
        print('PASS: normal-user alert editor, closed RSI waits for features, live price crossing on unviewed coin, deduplicated notifications and sound, Select All/Deselect All, Remember Me survives session reset/reload, logout revokes')


if __name__=='__main__': run(Path(sys.argv[1]).resolve(),scenario=exercise)
