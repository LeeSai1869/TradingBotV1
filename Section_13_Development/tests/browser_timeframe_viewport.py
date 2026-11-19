"""Real-chart LTF/HTF switches after hidden series have accumulated LTF data."""
import asyncio
from contextlib import closing
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in,settle
from Section_1_Global_Core.memory_storage.Storage import db,klines_store

async def exercise(base,library):
    with closing(klines_store.open_db()) as c:
        raw=klines_store.read_last_n(c,'BTCUSDT','1m',2200)
    db.write_features([dict(symbol='BTCUSDT',interval='1m',open_time=r[2],
        ema50=r[6],ema200=r[6],atr=2.,atr_ma=2.1) for r in raw])
    rows=[];features=[];end=1781654400000
    for i in range(450):
        t=end-(450-i)*3600000;price=60000+i*3
        rows.append(dict(symbol='BTCUSDT',interval='1h',open_time=t,close_time=t+3599999,
                         open=price,high=price+20,low=price-10,close=price+5,volume=10.))
        features.append(dict(symbol='BTCUSDT',interval='1h',open_time=t,ema50=price+5,ema200=price+5,atr=30.,atr_ma=31.))
    db.write_klines(rows);db.write_features(features)
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1500,'height':1000})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        await page.route('https://unpkg.com/**',lambda r:r.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000')
        async def switch(frame):
            await page.locator('#interval').select_option(frame)
            await page.wait_for_function('(frame)=>DataCache.timeframe===frame && !DataCache.loading && DataCache.bars.length>=400',arg=frame)
            await settle(page)
            await page.wait_for_timeout(100)
        await switch('1m')
        await page.evaluate("""()=>{
            Composer.config.featureStyles.ema200={...Composer.config.featureStyles.ema200,visible:true};
            Composer.config.featureStyles.atr={...Composer.config.featureStyles.atr,visible:true};
            Composer.config.featureStyles.atr_ma={...Composer.config.featureStyles.atr_ma,visible:true};
            dispatchEvent(new Event('chart-settings-change'));
        }""")
        await settle(page)
        await page.evaluate("""()=>{
            Composer.config.featureStyles.ema200.visible=false;
            Composer.config.featureStyles.atr_ma.visible=false;
            Canvas.chart.priceScale('right').applyOptions({autoScale:false});
            dispatchEvent(new Event('chart-settings-change'));
        }""")
        await settle(page)
        for frame in ('1h','1m','15m','1h'):
            await switch(frame)
            state=await page.evaluate("""async()=>{
                const candles=(await import('/overlays/candles/index.js')).getSeries();
                const scale=Canvas.chart.timeScale(),width=scale.width();
                const points=candles.data();
                const visible=points.filter(p=>{const x=scale.timeToCoordinate(p.time);return x!==null&&x>=0&&x<=width;});
                const last=points.at(-1),lastX=scale.timeToCoordinate(last.time);
                return {count:visible.length,lastX,width,range:scale.getVisibleLogicalRange(),auto:Canvas.chart.priceScale('right').options().autoScale,
                    hidden:Canvas.chart.panes().flatMap(p=>p.getSeries()).filter(s=>!s.options().visible).reduce((n,s)=>n+s.data().length,0)};
            }""")
            assert 195<=state['count']<=205,(frame,state)
            assert 0<=state['lastX']<=state['width'],(frame,state)
            assert state['auto'],(frame,state)
            assert state['hidden']==0,(frame,state)
            assert 'candles in view' in await page.locator('#status').inner_text()
        await page.screenshot(path='/tmp/chart-timeframe-desktop.png')
        await page.set_viewport_size({'width':600,'height':900})
        await switch('1m')
        narrow=await page.evaluate("""async()=>{
            const series=(await import('/overlays/candles/index.js')).getSeries();
            const scale=Canvas.chart.timeScale(),width=scale.width();
            return {width,spacing:scale.options().barSpacing,count:series.data().filter(p=>{
                const x=scale.timeToCoordinate(p.time);return x!==null&&x>=0&&x<=width;
            }).length};
        }""")
        assert 30<=narrow['count']<200,narrow
        assert narrow['spacing']>=4.5,narrow
        await page.screenshot(path='/tmp/chart-timeframe-narrow.png')
        assert not errors,errors
        print('PASS: BTC 1m/15m/1h switches keep 200 readable candles, latest candle visible, autoscale reset, no stale hidden-series timestamps')
        await browser.close()

if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
