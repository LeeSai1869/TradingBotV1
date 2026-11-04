"""Actual event viewer module: stages, time fields, paging and chart navigation."""
import asyncio
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.async_api import async_playwright

ROOT=Path(__file__).parents[1]/'Section_11_UI_UX'

async def main():
    requests=[];errors=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        try:
            page=await browser.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            async def route(request):
                parsed=urlparse(request.request.url)
                if parsed.path=='/':return await request.fulfill(content_type='text/html',body='<main id="events"></main><script type="module">window.DataCache={symbol:"BTCUSDT",timeframe:"5m"};window.jumps=[];window.openAlertChart=async e=>jumps.push(e);import {mountEvents} from "/controls/events/index.js";mountEvents(document.getElementById("events"));</script>')
                if parsed.path=='/api/events/history':
                    requests.append(parse_qs(parsed.query))
                    return await request.fulfill(json=dict(symbol='BTCUSDT',timeframe='5m',status='READY',scanned=10,has_more=True,next_before=300000,warnings=[],catalog=dict(events={'DI_HIGH_CONFIRMED':dict(stage='CONFIRMED',description='Existing anchor turn')}),events=[dict(type='DI_CANDIDATE_HIGH_UPDATED',stage='CANDIDATE',channel='di_plus',value=40,origin_time=None,known_time=600000,observed_open=300000,symbol='BTCUSDT',timeframe='5m',details={}),dict(type='DI_HIGH_CONFIRMED',stage='CONFIRMED',channel='di_plus',value=40,origin_time=0,known_time=900000,observed_open=600000,symbol='BTCUSDT',timeframe='5m',details=dict(qualified=True))]))
                path=ROOT/parsed.path.lstrip('/')
                if path.is_file():return await request.fulfill(path=str(path),content_type='text/javascript')
                await request.fulfill(status=404)
            await page.route('http://events.test/**',route);await page.goto('http://events.test/')
            await page.get_by_role('button',name='Load events',exact=True).wait_for()
            assert not requests
            await page.get_by_role('button',name='Load events',exact=True).click()
            await page.get_by_role('cell',name='DI HIGH CONFIRMED · di_plus',exact=True).wait_for()
            assert await page.locator('tbody tr').count()==2
            await page.get_by_label('Event stage',exact=True).select_option('CONFIRMED')
            assert await page.locator('tbody tr').count()==1
            await page.get_by_role('button',name='Chart',exact=True).click()
            assert await page.evaluate('jumps[0].bar_time')==600000 # confirmation candle, never origin
            assert await page.get_by_role('cell',name='Yes',exact=True).count()==1
            await page.get_by_role('button',name='Older events',exact=True).click()
            await page.wait_for_function("document.querySelector('button[type=submit]').disabled===false")
            assert requests[-1]['before']==['300000']
            await page.get_by_label('Event symbol',exact=True).fill('ETHUSDT');await page.get_by_label('Event timeframe',exact=True).select_option('15m')
            assert await page.get_by_role('button',name='Older events',exact=True).is_disabled()
            assert not errors,errors
            print('PASS manual load, candidate/confirmed separation, qualification, causal chart jump and pagination')
        finally:await browser.close()

if __name__=='__main__':asyncio.run(main())
