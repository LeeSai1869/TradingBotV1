"""Real chart primitive, user toggle, request scope and no price-scale changes."""
import asyncio
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
ROOT=Path(__file__).parents[1]
async def main():
    errors=[];requests=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        try:
            page=await browser.new_page(viewport=dict(width=1100,height=700));page.on('pageerror',lambda error:errors.append(str(error)))
            async def route(route):
                path=urlparse(route.request.url).path
                if path=='/':return await route.fulfill(content_type='text/html',body='''<link rel="stylesheet" href="/web_root/styles.css"><div id="toolbar"></div><div id="chart" style="position:relative;width:1000px;height:600px"></div><script src="/vendor.js"></script><script type="module">
import * as candles from '/overlays/candles/index.js';import * as strategy from '/overlays/btc_strategy/index.js';
window.chart=LightweightCharts.createChart(document.getElementById('chart'),{width:1000,height:600});candles.mount(chart);
window.series=candles.getSeries();series.setData(Array.from({length:20},(_,i)=>({time:300*(i+1),open:100,high:101,low:99,close:100.5})));chart.timeScale().fitContent();
window.data={symbol:'BTCUSDT',timeframe:'5m',atLiveEdge:true};strategy.mount();window.change=async()=>strategy.update(chart,data);await change();window.ready=true;
</script>''')
                if path=='/vendor.js':return await route.fulfill(path=str(ROOT/'packaging/vendor/lightweight-charts.js'),content_type='text/javascript')
                if path=='/api/strategy/btc':
                    requests.append(route.request.url)
                    return await route.fulfill(json=dict(status='READY',candles=20,trades=[dict(entry_time=900000,entry=100,exit_time=1500000,exit=100.7,status='CLOSED')],levels=[dict(time=t,entry_time=900000,entry=100,hard_stop=99.5,stop=99.5) for t in [900000,1200000,1500000]],observations=[dict(time=600000,price=99.2)],gaps=0))
                file=ROOT/'Section_11_UI_UX'/path.lstrip('/')
                await route.fulfill(path=str(file),content_type='text/css' if file.suffix=='.css' else 'text/javascript')
            await page.route('http://btc.test/**',route);await page.goto('http://btc.test/');await page.wait_for_function('window.ready')
            assert not requests
            assert await page.locator('#toolbar #btc-strategy-controls').count()==1
            assert await page.get_by_role('checkbox',name='Show BTC strategy flags').is_visible()
            await page.wait_for_timeout(100)
            before=await page.evaluate('series.priceToCoordinate(100)')
            await page.get_by_role('checkbox').check();await page.get_by_text('Simulated ·',exact=False).wait_for()
            await page.wait_for_timeout(100)
            assert len(requests)==1
            assert 'days=90' in requests[0]
            assert await page.evaluate('series.priceToCoordinate(100)')==before
            await page.evaluate('change()');assert len(requests)==1
            await page.get_by_label('BTC strategy history').select_option('365')
            await page.get_by_text('Simulated ·',exact=False).wait_for()
            assert len(requests)==2 and 'days=365' in requests[-1]
            await page.reload();await page.wait_for_function('window.ready');await page.get_by_text('Simulated ·',exact=False).wait_for()
            assert await page.get_by_role('checkbox',name='Show BTC strategy flags').is_checked()
            assert await page.get_by_label('BTC strategy history').input_value()=='365'
            assert len(requests)==3
            await page.screenshot(path='/tmp/btc-strategy.png')
            await page.evaluate("data.symbol='ETHUSDT';change()")
            assert await page.get_by_role('checkbox').is_disabled()
            assert len(requests)==3
            assert not errors,errors
            print('PASS real chart overlay, toggle, BTC scope, bounded polling, unchanged autoscale')
        finally:await browser.close()
if __name__=='__main__':asyncio.run(main())
