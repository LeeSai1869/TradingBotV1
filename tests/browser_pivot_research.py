"""Real chart plus manual compressed cohort, all-feature case table and navigation."""
import asyncio
import gzip
import json
import sys
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
ROOT=Path(__file__).parents[1]

async def main():
    errors=[];requests=[]
    pivot=dict(id='1'*64,type='PIVOT_LOW',price=99,origin_time=600000,confirmation_time=1200000,known_time=1500000)
    case=dict(id=pivot['id'],pivot=pivot,side='BUY_SIDE',origin=dict(status='HIT',max_favorable_pct=3,first_hit=dict(bars=2),complete=True),after_known=dict(status='NO_HIT',max_favorable_pct=1),origin_hit_by_confirmation=True,next_opposite=dict(origin_time=1800000))
    context=dict(status='READY',symbol='BTCUSDT',timeframe='15m',pivot=pivot,bars=[dict(client=dict(open_time=t,close_time=t+299999,open=100,high=101,low=99,close=100.5,volume=50),features=dict(di_plus=20,di_minus=30,adx=25,rsi=40,atr=.3,custom_feature=123),feature_status='VALID',availability='BEFORE_CONFIRMATION') for t in [300000,600000,900000,1200000,1500000]])
    report=dict(version='pivot-moves-v1',symbol='BTCUSDT',timeframe='15m',cases=[case],source_id='source',observed_as_of=2100000,config=dict(horizon_bars=None,threshold_pct=2),context_config=dict(before=12,after=24),contexts={case['id']:context})
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        try:
            page=await browser.new_page(viewport=dict(width=1400,height=1000));page.on('pageerror',lambda error:errors.append(str(error)))
            async def route(route):
                parsed=urlparse(route.request.url)
                if parsed.path=='/':return await route.fulfill(content_type='text/html',body='''<div id="chart" style="position:relative;width:900px;height:400px"></div><main id="study"></main><script src="/vendor.js"></script><script type="module">
import * as candles from '/overlays/candles/index.js';import * as visual from '/overlays/pivot_research/index.js';import {mountPivotResearch} from '/controls/pivot_research/index.js';
window.chart=LightweightCharts.createChart(document.getElementById('chart'),{width:900,height:400});candles.mount(chart);window.series=candles.getSeries();series.setData(Array.from({length:12},(_,i)=>({time:300*(i+1),open:100,high:101,low:99,close:100.5})));chart.timeScale().fitContent();
window.DataCache={symbol:'BTCUSDT',timeframe:'15m'};window.jumps=[];window.openAlertChart=async e=>jumps.push(e);visual.mount();visual.update(chart,DataCache);mountPivotResearch(document.getElementById('study'));window.ready=true;
</script>''')
                if parsed.path=='/vendor.js':return await route.fulfill(path=str(ROOT/'packaging/vendor/lightweight-charts.js'),content_type='text/javascript')
                if parsed.path=='/api/pivots/context':
                    requests.append(route.request.url)
                    return await route.fulfill(status=409,json=dict(error='Feature generation differs'))
                file=ROOT/'Section_11_UI_UX'/parsed.path.lstrip('/')
                await route.fulfill(path=str(file),content_type='text/javascript')
            await page.route('http://pivots.test/**',route);await page.goto('http://pivots.test/');await page.wait_for_function('window.ready')
            assert not requests
            await page.get_by_label('Pivot study report',exact=True).set_input_files(dict(name='study.json.gz',mimeType='application/gzip',buffer=gzip.compress(json.dumps(report).encode())))
            await page.get_by_role('button',name='Inspect pivot',exact=True).click()
            await page.get_by_role('button',name='Show pivot on chart',exact=True).wait_for()
            assert not requests # embedded context is a frozen snapshot
            assert await page.get_by_role('table',name='Pivot candle features').locator('tbody tr').count()==5
            await page.get_by_label('Pivot feature',exact=True).select_option('custom_feature')
            assert await page.get_by_role('cell',name='123',exact=True).count()==5
            before=await page.evaluate('series.priceToCoordinate(100)')
            await page.get_by_role('button',name='Show pivot on chart',exact=True).click();await page.wait_for_timeout(100)
            assert await page.evaluate('jumps[0].bar_time')==600000
            assert await page.evaluate('series.priceToCoordinate(100)')==before
            await page.get_by_label('Bars before',exact=True).fill('5')
            await page.get_by_role('button',name='Inspect pivot',exact=True).click()
            await page.get_by_text('Feature generation differs',exact=True).wait_for()
            assert len(requests)==1
            if len(sys.argv)>1:
                await page.reload();await page.wait_for_function('window.ready');requests.clear()
                await page.get_by_label('Pivot study report',exact=True).set_input_files(str(Path(sys.argv[1]).resolve()))
                await page.get_by_role('button',name='Inspect pivot',exact=True).first.wait_for(timeout=120000)
                text=await page.locator('#study [role=status]').first.inner_text();assert '103127 pivots in cohort' in text,text
                await page.get_by_role('button',name='Inspect pivot',exact=True).first.click()
                await page.get_by_role('button',name='Show pivot on chart',exact=True).wait_for()
                assert await page.get_by_role('table',name='Pivot candle features').locator('tbody tr').count()>0
                assert not requests
                print('PASS real 171 MiB expanded report: 103127 cases and frozen all-feature context',flush=True)
            assert not errors,errors
            print('PASS compressed report, embedded full features, per-case request, source rejection, chart navigation and unchanged scale')
        finally:await browser.close()
if __name__=='__main__':asyncio.run(main())
