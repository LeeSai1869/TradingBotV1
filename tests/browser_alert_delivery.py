"""Real notification control: open-app delivery, suspend/resume and network recovery.

No production database, exchange request or live notification permission is used.
Run: PYTHONPATH=. python3 tests/browser_alert_delivery.py
"""
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.async_api import async_playwright

ROOT=Path(__file__).parents[1]/'Section_11_UI_UX'

async def main():
    events=[];requests=[];errors=[];offline=False
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        try:
            page=await browser.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            await page.add_init_script('''
                window.AppSession={username:'test'};window.notices=[];window.notes=0;
                window.Notification=class {static permission='granted';constructor(title){notices.push(title);}close(){}};
                window.AudioContext=class {constructor(){this.state='running';this.currentTime=0;this.destination={};}async resume(){};
                createOscillator(){return {frequency:{value:0},connect(){},start(){notes++;},stop(){}};}
                createGain(){return {gain:{setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){}};}};
            ''')
            async def route(request):
                parsed=urlparse(request.request.url)
                if parsed.path=='/':
                    return await request.fulfill(content_type='text/html',body='<div id="toolbar"></div><button id="gesture">Enable audio</button><script type="module">import {mount} from "/controls/alerts/index.js";mount();window.ready=true;</script>')
                if parsed.path=='/api/alerts/signals':
                    return await request.fulfill(json=dict(enabled=True,notify=True,app=True,buy='chime',sell='bell'))
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
            assert not errors,errors
            print('PASS: open app receives live cards, desktop notifications and sounds; restore/reconnect preserves cursor without replaying history')
        finally:await browser.close()

if __name__=='__main__':asyncio.run(main())
