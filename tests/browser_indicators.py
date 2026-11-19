"""Completed indicators render in synchronized panes with independent settings."""
import asyncio
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from browser_smoke import run, sign_in, settle, db


async def exercise(base,library):
    rows=db.read_last_klines('BTCUSDT','15m',100)
    db.write_features([dict(symbol='BTCUSDT',interval='15m',open_time=row[2],ema50=row[6]-.5,
        wma50=row[6]-.3,rsi=45+i%25,adx=25+i%10,di_plus=30,di_minus=15,di_direction=15,di_spread=15,di_dominance=1/3,
        atr=2.5,atr_ma=2.2,volume_ma=9,vwap=row[6]-.2,vwap_upper1=row[6]+1,vwap_lower1=row[6]-1) for i,row in enumerate(rows)])
    last_open = rows[-1][2]
    db.write_klines([
        dict(symbol='BTCUSDT', interval='5m', open_time=last_open - (2100-i)*300_000,
             close_time=last_open - (2099-i)*300_000 - 1, open=237, high=241, low=235,
             close=239, volume=11, quote_volume=2620.0)
        for i in range(2100)
    ])
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1800,'height':1200})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('console',lambda message:errors.append(f"{message.text} ({message.location})") if message.type=='error' else None)
        requests=[];page.on('request',lambda request:requests.append(request.url))
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000 && !DataCache._olderPromise')
        await page.evaluate("window.dispatchEvent(new CustomEvent('open-feature-settings', {detail:'WMA'}))")
        settings=page.get_by_role('dialog',name='Settings',exact=True)
        await settings.get_by_role('button',name='Display',exact=True).click()
        for feature,fields in [('WMA',['WMA 50']),('RSI',['RSI']),('ADX',['ADX']),('DI',['+DI','−DI','DI dominance']),('ATR',['ATR']),('Volume',['Volume','Volume average','Volume in USDT']),('VWAP',['VWAP','Upper band 1','Lower band 1'])]:
            await settings.get_by_role('button',name=feature,exact=True).click()
            for field in fields:await settings.get_by_label(field,exact=True).check()
        await settings.get_by_role('tab',name='Candles',exact=True).click()
        await settings.get_by_role('button',name='Style',exact=True).click()
        await settings.get_by_label('Bullish body',exact=True).fill('#123abc')
        await settings.get_by_label('Bearish wick',exact=True).fill('#ff00ab')
        await settings.get_by_label('Show borders',exact=True).check()
        await settings.get_by_role('button',name='Apply',exact=True).click();await settle(page)
        await page.wait_for_function('Canvas.chart.panes().length===6')
        assert await page.evaluate("Canvas.chart.panes()[0].getSeries()[0].options().upColor")=='#123abc'
        assert await page.evaluate("Canvas.chart.panes()[0].getSeries()[0].options().wickDownColor")=='#ff00ab'
        assert await page.evaluate("Canvas.chart.panes()[0].getSeries()[0].options().borderVisible") is True
        assert await page.evaluate("(async()=>{const x=await import('/overlays/indicators/index.js');return x.getSeries('wma50').options().visible && x.getSeries('wma50').getPane().paneIndex()===0 && x.getSeries('adx').options().title==='';})()")
        for feature in ['RSI','ADX','DI','ATR','Volume']:
            await page.get_by_role('group',name=f'{feature} pane controls').wait_for()
        assert await page.evaluate("(async()=>{const x=await import('/overlays/indicators/index.js');return x.getSeries('rsi').data().at(-1).value;})()") == 69
        await page.mouse.move(1,1);await settle(page)
        rsi_label=await page.locator('.indicator-values[aria-label="RSI values"]').inner_text()
        assert rsi_label=='RSI 69.00',rsi_label
        assert await page.locator('.indicator-values[aria-label="ADX values"]').inner_text()=='ADX 34.00'
        assert 'DI dominance 0.33' in await page.locator('.indicator-values[aria-label="DI values"]').inner_text()
        assert await page.evaluate("(async()=>{const x=await import('/overlays/indicators/index.js');return x.getSeries('vwap').getPane().paneIndex();})()") == 0
        assert await page.evaluate("(async()=>{const x=await import('/overlays/indicators/index.js');return x.getSeries('adx').getPane().paneIndex()!==x.getSeries('di_plus').getPane().paneIndex() && x.getSeries('adx').priceLines().some(line=>line.options().price===25) && x.getSeries('vwap_upper1').options().title==='';})()")
        assert await page.evaluate("(async()=>{const x=await import('/overlays/indicators/index.js');return ['rsi','adx','atr','vwap'].every(key=>x.getSeries(key).priceFormatter().format(34.40199)==='34.40');})()")
        assert await page.evaluate("Canvas.chart.panes()[0].getSeries().filter(s=>s.options().title==='EMA 50' || s.options().color===Composer.config.featureStyles.ema50.color).some(s=>s.options().lastValueVisible && s.priceFormatter().format(34.40199)==='34.40')")
        assert 'O' in await page.get_by_role('region',name='Candle details').inner_text()
        details=page.get_by_role('region',name='Candle details')
        assert await details.locator('dt[title="Volume"]').locator('xpath=following-sibling::dd[1]').inner_text()==await page.evaluate('DataCache.bars.at(-1).client.volume.toFixed(2)')
        assert 'USDT' in await page.locator('.indicator-values[aria-label="Volume values"]').inner_text()
        assert '≈' in await details.inner_text()
        await page.evaluate("""async()=>{
            const indicators=await import('/overlays/indicators/index.js');
            const bar=DataCache.bars.at(-1);
            indicators.updateLive(Canvas.chart,{...bar,features:{...bar.features,rsi:61}});
            if(indicators.getSeries('rsi').data().at(-1).value!==61)throw Error('Live RSI did not update');
            indicators.updateLive(Canvas.chart,bar);
            const candle=Canvas.chart.panes()[0].getSeries()[0];
            const previous=DataCache.bars.at(-2);
            Canvas.chart.setCrosshairPosition(previous.client.close,previous.time,candle);
        }""")
        assert 'Closed' in await page.locator('#candle-details').get_attribute('title')
        await page.get_by_role('button',name='Collapse RSI',exact=True).click();await settle(page)
        assert await page.evaluate('Canvas.chart.panes()[1].getHeight()')<=40
        await page.get_by_role('button',name='Expand RSI',exact=True).click()
        await page.get_by_role('button',name='RSI settings',exact=True).click()
        await settings.get_by_label('RSI lower reference level',exact=True).fill('25')
        await settings.get_by_label('RSI upper reference level',exact=True).fill('75')
        await settings.get_by_label('RSI color',exact=True).fill('#12abef')
        await settings.get_by_role('button',name='Apply',exact=True).click();await settle(page)
        assert await page.evaluate('Composer.config.rsiLevels.lower')==25
        assert await page.evaluate("(async()=>{const x=await import('/overlays/indicators/index.js');return x.getSeries('rsi').options().color;})()")=='#12abef'
        await page.get_by_role('button',name='Volume settings',exact=True).click()
        await settings.get_by_role('button',name='Style',exact=True).click()
        await settings.get_by_label('Volume display',exact=True).select_option('line')
        await settings.get_by_label('Volume width',exact=True).select_option('4')
        await settings.get_by_label('Volume line style',exact=True).select_option('2')
        await settings.get_by_label('Volume color',exact=True).fill('#18abfe')
        await settings.get_by_role('button',name='Apply',exact=True).click();await settle(page)
        await page.evaluate("""async()=>{
            const indicators=await import('/overlays/indicators/index.js');
            const series=indicators.getSeries('volume');
            const {lineWidth,lineStyle,color}=series.options();
            if(series.seriesType()!=='Line'||lineWidth!==4||lineStyle!==2||color!=='#18abfe')
                throw Error('Volume line style did not apply');
            const bar=DataCache.bars.at(-1);
            indicators.updateLive(Canvas.chart,{...bar,client:{...bar.client,volume:123.45,quote_volume:246.9}});
            if(series.data().at(-1).value!==123.45 || indicators.getSeries('volume_usdt').data().at(-1).value!==246.9)
                throw Error('Volume series missed live update');
        }""")
        await page.get_by_role('button',name='Close RSI',exact=True).click();await settle(page)
        assert await page.evaluate('Canvas.chart.panes().length')==5
        assert not await page.get_by_role('group',name='RSI pane controls').count()
        await page.reload();await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000')
        await settle(page)
        assert await page.evaluate('Canvas.chart.panes().length')==5
        assert await page.evaluate('Composer.config.featureStyles.rsi.visible') is False
        assert await page.evaluate("Composer.config.featureStyles.volume.presentation === 'line' && Composer.config.featureStyles.volume.style === 2")
        requested, release = asyncio.Event(), asyncio.Event()
        five_minute_pages = []

        async def delay_btc_five_minute(route):
            if 'interval=5m' in route.request.url:
                five_minute_pages.append(route.request.url)
                if 'before=' not in route.request.url:
                    requested.set()
                    await release.wait()
            await route.continue_()

        async def latest_candle():
            return await page.evaluate("Canvas.chart.panes()[0].getSeries()[0].data().at(-1)")
        await page.route('**/api/bars?*', delay_btc_five_minute)
        await page.evaluate('Canvas.chart.timeScale().setVisibleLogicalRange({from:1300,to:2000})')
        await settle(page)
        await page.locator('#interval').select_option('5m')
        try:
            await asyncio.wait_for(requested.wait(), timeout=5)
            await settle(page)
            assert await latest_candle() is None
        finally:
            release.set()
        await page.wait_for_function("!DataCache.loading && DataCache.bars.length === 2000 && !DataCache._olderPromise")
        await settle(page)
        assert (await latest_candle())['close'] == 239
        visible = await page.evaluate('Canvas.chart.timeScale().getVisibleLogicalRange()')
        assert 115 <= visible['to'] - visible['from'] <= 130, visible
        assert len(five_minute_pages) == 2, five_minute_pages
        volume_values = page.locator('.indicator-values[aria-label="Volume values"]')
        assert '2,620 USDT' in await volume_values.inner_text()
        assert '11.00 BTC' in await volume_values.inner_text()
        assert await volume_values.locator('span').all_text_contents() == ['11.00 BTC', '— BTC', '2,620 USDT']
        assert not await page.get_by_role('group',name='Volume pane controls').get_by_text('Volume',exact=True).count()
        await page.get_by_role('button',name='Volume settings',exact=True).click()
        await settings.get_by_label('Volume in USDT',exact=True).uncheck()
        await settings.get_by_role('button',name='Apply',exact=True).click()
        await settle(page)
        assert '11.00 BTC' in await volume_values.inner_text()
        assert 'USDT' not in await volume_values.inner_text()
        await page.get_by_role('button',name='Volume settings',exact=True).click()
        await settings.get_by_label('Volume in USDT',exact=True).check()
        await settings.get_by_label('Volume',exact=True).uncheck()
        await settings.get_by_role('button',name='Apply',exact=True).click()
        await settle(page)
        assert '2,620 USDT' in await volume_values.inner_text()
        assert '11.00 BTC' not in await volume_values.inner_text()
        await page.unroute('**/api/bars?*', delay_btc_five_minute)
        # Dense BTC depth packets must render and leave the main time scale draggable.
        await page.evaluate("""async () => {
            const {update} = await import('/overlays/liquidity/index.js');
            Composer.config.featureStyles.liquidity_bids.visible = true;
            Composer.config.featureStyles.liquidity_heatmap.visible = true;
            const bars = DataCache.bars;
            const start = bars.at(-2).open_time - 1200000;
            const bands = Array.from({length: 550}, (_, i) => ({
                side:'bid', low:236 + i/1000, high:236.001 + i/1000, notional_usdt:1000+i
            }));
            const history = Array.from({length:240}, (_, i) => ({
                observed:true, market:'usdt_perpetual', bands, metrics:{mid:240},
                sampled_ms:start+i*5000, available_ms:start+i*5000, book_received_ms:start+i*5000
            }));
            update(Canvas.chart, {bars, liquidity:{status:'stale', history}});
        }""")
        await settle(page)
        target=await page.locator('#chart canvas').first.bounding_box()
        x=target['x']+target['width']*.6
        y=target['y']+target['height']*.4
        before=await page.evaluate("Canvas.chart.timeScale().getVisibleLogicalRange().from")
        await page.mouse.move(x,y)
        await page.mouse.down()
        await page.mouse.move(x+150,y,steps=10)
        await page.mouse.up()
        await settle(page)
        after=await page.evaluate("Canvas.chart.timeScale().getVisibleLogicalRange().from")
        assert after < before - 1, (before, after)
        assert not errors,errors
        forbidden=['/api/chart_window','/api/flags_current','/api/live_candle']
        assert not any(any(path in url for path in forbidden) for url in requests)
        print('PASS: RSI/ADX/ATR/Volume native panes, VWAP overlay, axis labels, collapse/close/direct settings, RSI levels/styles, persistence, candle details; no separate feature requests',flush=True)
        await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
