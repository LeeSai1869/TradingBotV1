"""Real notification control: open-app delivery, suspend/resume and network recovery.

No production database, exchange request or live notification permission is used.
Run: PYTHONPATH=. python3 tests/browser_alert_delivery.py
"""
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.async_api import async_playwright

ROOT=Path(__file__).parents[1]/'Section_11_UI_UX'

async def main():
    events=[];requests=[];errors=[];patches=[];rules=[];offline=False;save_failed=False;catalog_failed=True;rule_save_failed=False
    prefs=dict(enabled=True,notify=True,app=True,buy='chime',sell='bell',buy_notify=True,sell_notify=True,
               mobile=True,coins={'ENAUSDT':{'desktop':True,'mobile':False}},timeframes={'5m':{'mobile':True}})
    mobile_before=json.dumps({key:prefs[key] for key in ('mobile','coins','timeframes','buy_notify','sell_notify','enabled')},sort_keys=True)
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
        try:
            page=await browser.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            await page.add_init_script('''
                window.AppSession={username:'test'};window.notices=[];window.notes=0;window.permissionRequests=[];window.permissionResult='granted';
                window.Notification=class {static permission='default';static async requestPermission(){permissionRequests.push(navigator.userActivation.isActive);this.permission=permissionResult;return this.permission;}constructor(title){notices.push(title);}close(){}};
                window.AudioContext=class {constructor(){this.state='running';this.currentTime=0;this.destination={};}async resume(){};
                createOscillator(){return {frequency:{value:0},connect(){},start(){notes++;},stop(){}};}
                createGain(){return {gain:{setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){}};}};
            ''')
            async def route(request):
                parsed=urlparse(request.request.url)
                if parsed.path=='/':
                    return await request.fulfill(content_type='text/html',body='<div id="toolbar"><select id="symbol"><option>BTCUSDT</option><option>ENAUSDT</option></select><select id="interval"><option>5m</option><option>1m</option></select></div><button id="gesture">Enable audio</button><section id="settings"></section><script type="module">import {mount,renderNotificationSettings} from "/controls/alerts/index.js";mount();window.openSettings=()=>renderNotificationSettings(document.getElementById("settings"));window.ready=true;</script>')
                if parsed.path=='/api/alerts/signals':
                    if request.request.method=='POST':
                        patch=request.request.post_data_json;patches.append(patch)
                        if save_failed:return await request.fulfill(status=503,json=dict(error='Preferences unavailable'))
                        prefs.update(patch)
                    return await request.fulfill(json=prefs)
                if parsed.path=='/api/mobile/config':return await request.fulfill(json=dict(ready=True,reason='',origin=None))
                if parsed.path=='/api/alerts/catalog':
                    if catalog_failed:return await request.fulfill(status=503,json=dict(error='Alert catalog unavailable'))
                    return await request.fulfill(json=dict(symbols=['BTCUSDT','ENAUSDT'],intervals=['5m','1m'],fields={'client.close':'Close','decision.buy':'BUY signal','decision.sell':'SELL signal'},live_fields=['client.close'],operators=['above','equals'],sounds=['none']))
                if parsed.path=='/api/alerts':
                    if request.request.method=='POST':
                        if rule_save_failed:return await request.fulfill(status=503,json=dict(error='Alert save unavailable'))
                        spec=request.request.post_data_json
                        key=spec.get('id',str(len(rules)+1))
                        rules[:]=[rule for rule in rules if rule['id']!=key]
                        rules.append(dict(spec,id=key))
                        return await request.fulfill(json=dict(ok=True,id=key))
                    return await request.fulfill(json=dict(rules=rules))
                if parsed.path=='/api/alerts/events':
                    requests.append(request.request.url)
                    if offline:return await request.fulfill(status=503,json=dict(error='Temporary outage'))
                    after=parse_qs(parsed.query).get('after')
                    if after is None:return await request.fulfill(json=dict(cursor=9,events=[],history=[dict(seq=9,name='OLD',symbol='BTCUSDT',interval='5m',created=0,bar_time=0)]))
                    rows=[e for e in events if e['seq']>int(after[0])]
                    return await request.fulfill(json=dict(cursor=rows[-1]['seq'] if rows else int(after[0]),events=rows))
                file=ROOT/parsed.path.lstrip('/')
                if file.is_file():return await request.fulfill(path=str(file),content_type='text/javascript')
                await request.fulfill(status=404,body='not found')
            await page.route('http://alerts.test/**',route)
            await page.goto('http://alerts.test/')
            await page.wait_for_function('window.ready')
            add_alert=page.get_by_role('button',name='Alerts',exact=True)
            assert await page.evaluate('permissionRequests')==[]
            # Toolbar opens the editor directly; catalog failures are visible and retryable.
            await add_alert.click()
            await page.locator('#alerts-status').filter(has_text='Alert catalog unavailable').wait_for()
            assert await add_alert.is_enabled()
            catalog_failed=False
            for name in ('Price above 10','BUY BTCUSDT','SELL BTCUSDT'):
                await add_alert.click()
                editor=page.get_by_role('dialog',name='Alerts',exact=True)
                await editor.wait_for()
                assert await editor.get_by_role('tab').all_text_contents()==['Create Alert','Edit Alerts','Recent Alert History']
                assert await editor.get_by_label('Coin',exact=True).input_value()=='BTCUSDT'
                assert await editor.get_by_label('Timeframe',exact=True).input_value()=='5m'
                if name.startswith(('BUY','SELL')):
                    side=name.split()[0]
                    await editor.get_by_role('button',name=side+' signal',exact=True).click()
                    assert await editor.get_by_label('Field',exact=True).input_value()=='decision.'+side.lower()
                    assert await editor.get_by_label('Evaluation',exact=True).input_value()=='closed'
                else:
                    await editor.get_by_label('Coin',exact=True).select_option('ALL')
                    await editor.get_by_label('Timeframe',exact=True).select_option('ALL')
                    await editor.get_by_label('Alert name',exact=True).fill(name)
                    await editor.get_by_label('Threshold (signed numbers allowed)',exact=True).fill('10')
                    rule_save_failed=True
                    await editor.get_by_role('button',name='Create alert',exact=True).click()
                    await editor.get_by_role('status').filter(has_text='Alert save unavailable').wait_for()
                    assert await editor.is_visible()
                    assert await editor.get_by_label('Alert name',exact=True).input_value()==name
                    rule_save_failed=False
                await editor.get_by_role('button',name='Create alert',exact=True).click()
                await editor.get_by_role('tab',name='Edit Alerts',exact=True).wait_for()
                await page.wait_for_function("document.getElementById('alert-tab-edit').getAttribute('aria-selected')==='true'")
                await editor.locator('.notification-rule').filter(has_text=name).wait_for()
                assert 'Alert saved.' not in await page.locator('body').inner_text()
                await editor.get_by_role('button',name='Close alert editor',exact=True).click()
                await editor.wait_for(state='hidden')
                await page.wait_for_function("document.activeElement===document.getElementById('alerts-button')")
            assert [rule['name'] for rule in rules]==['Price above 10','BUY BTCUSDT','SELL BTCUSDT']
            assert all(rule['enabled'] and rule['notify'] for rule in rules)
            assert rules[0]['symbol']=='ALL' and rules[0]['interval']=='ALL'
            assert patches==[]
            assert await page.evaluate('permissionRequests')==[]
            assert await add_alert.inner_text()=='Alerts'
            assert await add_alert.get_attribute('aria-pressed') is None

            # Named saved alerts are visible and editable in Settings.
            await page.evaluate('openSettings()')
            row=page.locator('.notification-rule').filter(has_text='Price above 10')
            await row.get_by_role('button',name='Edit Price above 10',exact=True).click()
            editor=page.get_by_role('dialog',name='Alerts',exact=True)
            await editor.get_by_label('Alert name',exact=True).fill('Price above 10 edited')
            await editor.get_by_role('button',name='Save changes',exact=True).click()
            await editor.locator('.notification-rule').filter(has_text='Price above 10 edited').wait_for()
            await editor.get_by_role('button',name='Close alert editor',exact=True).click()
            await editor.wait_for(state='hidden')
            assert len(rules)==3 and rules[-1]['id']=='1'
            await page.get_by_role('button',name='Allow desktop notifications',exact=True).click()
            await page.get_by_text('Desktop notifications allowed and enabled.',exact=True).wait_for()
            await page.wait_for_function("!document.getElementById('alerts-button').disabled")
            assert await page.evaluate('permissionRequests')==[True]
            assert patches==[{'notify':True}]
            await page.get_by_role('button',name='Enable audio',exact=True).click()
            assert await page.locator('.alert-toast').count()==0
            def signal(seq,side):return dict(seq=seq,name=side,symbol='ENAUSDT',interval='5m',created=seq*1000,bar_time=seq*1000,sound='chime',notify=True,app=True,details=dict(side=side,price=.2,confidence=80))
            events.append(signal(10,'BUY'))
            await page.locator('.alert-toast').filter(has_text='ENAUSDT 5m BUY').wait_for()
            assert await page.evaluate('notices.length')==1
            assert await page.evaluate('notes')>0
            await page.evaluate("dispatchEvent(new Event('pagehide'))")
            count=len(requests);events.append(signal(11,'SELL'))
            await page.wait_for_timeout(2300);assert len(requests)==count
            await page.evaluate("dispatchEvent(new Event('pageshow'))")
            await page.locator('.alert-toast').filter(has_text='ENAUSDT 5m SELL').wait_for()
            assert await page.evaluate('notices.length')==2
            offline=True
            await page.evaluate("dispatchEvent(new Event('focus'))")
            await page.wait_for_function("document.getElementById('alerts-button').title.includes('retrying')")
            events.append(signal(12,'BUY'));offline=False
            await page.evaluate("dispatchEvent(new Event('online'))")
            await page.wait_for_function('notices.length===3')
            await page.wait_for_timeout(2300)
            assert await page.evaluate('notices.length')==3

            # Desktop toggles preserve every mobile and automatic-monitoring setting.
            desktop=page.get_by_label('Desktop notifications',exact=True)
            await desktop.uncheck()
            await page.wait_for_function("!document.querySelector('[name=notify]').disabled")
            assert prefs['notify'] is False
            assert await add_alert.inner_text()=='Alerts'
            await desktop.check()
            await page.wait_for_function("!document.querySelector('[name=notify]').disabled")
            assert prefs['notify'] is True
            assert await page.evaluate('permissionRequests')==[True]
            # Installed desktop app uses native IPC, including when browser notices are unavailable.
            await page.evaluate("window.nativeCalls=[];window.nativeFailure=false;window.__TAURI__={core:{invoke:async(command,args)=>{if(nativeFailure)throw Error('Native notification failed');nativeCalls.push({command,...args});}}}")
            events.append(signal(13,'BUY'))
            await page.evaluate("dispatchEvent(new Event('focus'))")
            await page.wait_for_function('nativeCalls.length===1')
            call=await page.evaluate('nativeCalls[0]')
            assert call['command']=='plugin:notification|notify'
            assert 'BUY' in call['options']['title']
            assert await page.evaluate('notices.length')==3
            events.append(signal(14,'SELL'))
            await page.evaluate("dispatchEvent(new Event('focus'))")
            await page.wait_for_function('nativeCalls.length===2')
            assert 'SELL' in await page.evaluate('nativeCalls[1].options.title')
            await page.evaluate('nativeFailure=true')
            events.append(signal(15,'BUY'))
            await page.evaluate("dispatchEvent(new Event('focus'))")
            await page.get_by_role('status').filter(has_text='Native notification failed').wait_for()
            assert await page.locator('.alert-toast').count()>0

            # Rejected/dismissed/unsupported permission never disables existing delivery.
            await desktop.uncheck()
            await page.wait_for_function("!document.querySelector('[name=notify]').disabled")
            count=len(patches)
            for permission in ('denied','default'):
                await page.evaluate('(value)=>{Notification.permission="default";permissionResult=value;}',permission)
                await page.get_by_role('button',name='Allow desktop notifications',exact=True).click()
                await page.wait_for_function("!document.querySelector('#settings button').disabled")
                assert len(patches)==count
                assert permission in await page.locator('#settings [role=status]').inner_text()
                assert prefs['notify'] is False
            await page.evaluate('window.SavedNotification=Notification;delete window.Notification')
            await page.get_by_role('button',name='Allow desktop notifications',exact=True).click()
            await page.locator('#settings [role=status]').filter(has_text='unavailable').wait_for()
            assert len(patches)==count
            await page.evaluate('window.Notification=SavedNotification;Notification.permission="granted"')
            save_failed=True
            await page.get_by_role('button',name='Allow desktop notifications',exact=True).click()
            await page.locator('#settings [role=status]').filter(has_text='Preferences unavailable').wait_for()
            assert await add_alert.is_enabled()
            assert prefs['notify'] is False
            save_failed=False

            # Settings permission button also enables delivery when the master switch was off.
            await page.evaluate('openSettings()')
            await page.get_by_role('button',name='Allow desktop notifications',exact=True).click()
            await page.get_by_text('Desktop notifications allowed and enabled.',exact=True).wait_for()
            assert prefs['notify'] is True
            assert await page.get_by_label('Desktop notifications',exact=True).is_checked()
            await page.get_by_label('Desktop notifications',exact=True).uncheck()
            await page.wait_for_function("!document.querySelector('[name=notify]').disabled")
            await page.evaluate('Notification.permission="default";permissionResult="denied"')
            count=len(patches)
            await page.get_by_label('Desktop notifications',exact=True).click()
            await page.wait_for_function("!document.querySelector('[name=notify]').disabled")
            assert not await page.get_by_label('Desktop notifications',exact=True).is_checked()
            assert len(patches)==count
            assert json.dumps({key:prefs[key] for key in ('mobile','coins','timeframes','buy_notify','sell_notify','enabled')},sort_keys=True)==mobile_before
            assert all(set(patch)=={'notify'} for patch in patches)
            assert not errors,errors
            print('PASS: Alerts creates price/BUY/SELL rules directly, retry and edit preserve identity, settings control delivery, native/browser delivery works and mobile preferences remain unchanged')
        finally:await browser.close()

if __name__=='__main__':asyncio.run(main())
