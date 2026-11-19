"""Signed-in market switches, viewport-error recovery and a settings/refresh race."""
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in,settle,db


async def exercise(base,library):
    end=1781654400000;step=900000
    rows=[];features=[]
    for i in range(2200):
        stamp=end-(2200-i)*step;price=3000+i*.01
        rows.append(dict(symbol='ETHUSDT',interval='15m',open_time=stamp,close_time=stamp+step-1,
            open=price,high=price+2,low=price-1,close=price+1,volume=100,quote_volume=300000))
        features.append(dict(symbol='ETHUSDT',interval='15m',open_time=stamp,ema50=price,volume_ma=321))
    db.write_klines(rows);db.write_features(features)
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1500,'height':1000})
        errors=[];expected=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        def console(message):
            if message.type=='error':
                if 'injected viewport failure' in message.text:expected.append(message.text)
                else:errors.append(message.text)
        page.on('console',console)
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        async def capture_series(route):
            response=await route.fetch();source=await response.text()
            source+="""
const originalInit=Canvas.init.bind(Canvas);Canvas.init=(...args)=>{
                const chart=originalInit(...args),add=chart.addSeries.bind(chart);window.marketSeries=[];
                chart.addSeries=(...params)=>{const series=add(...params);marketSeries.push(series);return series;};return chart;};
"""
            await route.fulfill(response=response,body=source)
        await page.route('**/chart/index.js',capture_series)
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('Composer?.mounted && !DataCache.loading && DataCache.bars.length===2000')
        await settle(page)
        # Inject one real chart API exception on the next dataset's viewport reset.
        await page.evaluate('''()=>{
            const scale=Canvas.chart.timeScale(),original=scale.setVisibleLogicalRange.bind(scale);
            scale.setVisibleLogicalRange=(...args)=>{scale.setVisibleLogicalRange=original;throw Error('injected viewport failure');};
            const select=document.getElementById('symbol');
            if(![...select.options].some(o=>o.value==='ETHUSDT'))select.add(new Option('ETHUSDT','ETHUSDT'));
            select.value='ETHUSDT';select.dispatchEvent(new Event('change'));
        }''')
        await page.wait_for_function("DataCache.symbol==='ETHUSDT'&&!DataCache.loading&&!DataCache._olderPromise&&DataCache.bars.length===2000")
        await settle(page)
        # A second full render must work after the exception, rather than freezing.
        await page.evaluate("Composer.config.featureStyles.ema50.visible=true;dispatchEvent(new Event('chart-settings-change'))")
        await settle(page)
        state=await page.evaluate('''async()=>{
            const {getSeries}=await import('/overlays/candles/index.js');
            return {symbols:[...new Set(DataCache.bars.map(b=>b.client.symbol))],
                rendered:getSeries().data().at(-1).close,stored:DataCache.bars.at(-1).client.close,
                feature:DataCache.bars.at(-1).features.ema50,
                plottedEMA:marketSeries.some(series=>{try{return series.data().at(-1)?.value===DataCache.bars.at(-1).features.ema50;}catch{return false;}})};
        }''')
        assert state['symbols']==['ETHUSDT'],state
        assert state['rendered']==state['stored'] and state['rendered']>3000,state
        assert state['feature']>3000 and state['plottedEMA'],state
        assert expected,'viewport exception was not exercised'
        # Change volume settings while a metadata render is already pending.
        await page.get_by_role('button',name='Open settings',exact=True).click()
        dialog=page.get_by_role('dialog',name='Settings')
        await dialog.get_by_role('tab',name='Features',exact=True).click()
        await dialog.get_by_role('button',name='Volume',exact=True).click()
        await dialog.get_by_label('Volume average',exact=True).check()
        await dialog.get_by_label('Volume average width',exact=True).select_option('4')
        await dialog.get_by_label('Volume average line style',exact=True).select_option('2')
        await page.evaluate('''()=>{
            DataCache.emit('stored-refresh');
            document.querySelector('.settings-apply').click();
            DataCache.emit('stored-refresh');
        }''')
        await settle(page)
        line=await page.evaluate("import('/overlays/indicators/index.js').then(m=>({options:m.getSeries('volume_ma').options(),last:m.getSeries('volume_ma').data().at(-1)}))")
        assert line['options']['visible'] and line['options']['lineWidth']==4 and line['options']['lineStyle']==2,line
        assert line['last']['value']==321,line
        # A correctly labeled envelope with BTC candle contents must still fail closed.
        async def mismatch(route):
            response=await route.fetch();packet=await response.json()
            if packet.get('bars'):packet['bars'][0]['client']['symbol']='BTCUSDT'
            await route.fulfill(response=response,json=packet)
        await page.route('**/api/bars?**',mismatch)
        await page.locator('#reload').click()
        await page.wait_for_function("DataCache.error?.includes('Rejected mismatched chart response')")
        assert await page.evaluate('DataCache.bars.length')==0
        assert await page.evaluate("import('/overlays/candles/index.js').then(m=>m.getSeries().data().length)")==0
        await page.unroute('**/api/bars?**')
        await page.locator('#reload').click()
        await page.wait_for_function("!DataCache.loading&&DataCache.bars.length===2000&&!DataCache._olderPromise")
        await settle(page)
        assert await page.evaluate("DataCache.bars.every(b=>b.symbol==='ETHUSDT'&&b.client.symbol==='ETHUSDT')")
        assert not errors,errors
        print('PASS: signed-in BTC/ETH switch, render-exception recovery, volume-settings refresh race, mismatched-market rejection and reload recovery',flush=True)
        await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
