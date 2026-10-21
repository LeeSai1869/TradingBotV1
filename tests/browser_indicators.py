"""Completed indicators render in synchronized panes with independent settings."""
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from browser_smoke import run, sign_in, settle, db


async def exercise(base,library):
    rows=db.read_last_klines('BTCUSDT','15m',100)
    db.write_features([dict(symbol='BTCUSDT',interval='15m',open_time=row[2],ema50=row[6]-.5,
        wma50=row[6]-.3,rsi=45+i%25,adx=25+i%10,di_plus=30,di_minus=15,di_direction=15,di_spread=15,di_dominance=1/3,
        atr=2.5,atr_ma=2.2,volume_ma=9,vwap=row[6]-.2,vwap_upper1=row[6]+1,vwap_lower1=row[6]-1) for i,row in enumerate(rows)])
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1800,'height':1200})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('console',lambda message:errors.append(message.text) if message.type=='error' else None)
        requests=[];page.on('request',lambda request:requests.append(request.url))
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000 && !DataCache._olderPromise')
        await page.get_by_role('button',name='Open settings',exact=True).click()
        settings=page.get_by_role('dialog',name='Settings',exact=True)
        await settings.get_by_role('tab',name='Features',exact=True).click()
        for feature,fields in [('WMA',['WMA 50']),('RSI',['RSI']),('ADX',['ADX']),('DI',['+DI','−DI','DI dominance']),('ATR',['ATR']),('Volume',['Volume','Volume average']),('VWAP',['VWAP','Upper band 1','Lower band 1'])]:
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
        assert await page.evaluate("(async()=>{const x=await import('/overlays/indicators/index.js');return ['rsi','adx','atr','volume','vwap'].every(key=>x.getSeries(key).priceFormatter().format(34.40199)==='34.40');})()")
        assert await page.evaluate("Canvas.chart.panes()[0].getSeries().filter(s=>s.options().title==='EMA 50' || s.options().color===Composer.config.featureStyles.ema50.color).some(s=>s.options().lastValueVisible && s.priceFormatter().format(34.40199)==='34.40')")
        assert 'O' in await page.get_by_role('region',name='Candle details').inner_text()
        details=page.get_by_role('region',name='Candle details')
        assert await details.locator('dt').filter(has_text='Vol').locator('xpath=following-sibling::dd[1]').inner_text()==await page.evaluate('DataCache.bars.at(-1).client.volume.toFixed(2)')
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
        await page.get_by_role('button',name='Close RSI',exact=True).click();await settle(page)
        assert await page.evaluate('Canvas.chart.panes().length')==5
        assert not await page.get_by_role('group',name='RSI pane controls').count()
        await page.reload();await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000')
        await settle(page)
        assert await page.evaluate('Canvas.chart.panes().length')==5
        assert await page.evaluate('Composer.config.featureStyles.rsi.visible') is False
        assert not errors,errors
        forbidden=['/api/chart_window','/api/flags_current','/api/live_candle']
        assert not any(any(path in url for path in forbidden) for url in requests)
        print('PASS: RSI/ADX/ATR/Volume native panes, VWAP overlay, axis labels, collapse/close/direct settings, RSI levels/styles, persistence, candle details; no separate feature requests',flush=True)
        await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
