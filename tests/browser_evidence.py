"""Disposable closed-feature scenarios, real chart; no exchange or order calls."""
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in,settle,db


async def exercise(base,library):
    rows=db.read_last_klines('BTCUSDT','15m',100);price=rows[-1][6]
    db.write_features([dict(symbol='BTCUSDT',interval='15m',open_time=r[2],formula_version=3,
        atr=2,ema50=price-2,ema200=price-5,vwap=price-1,rsi=65,di_plus=30,di_minus=10,di_spread=20,adx=32,
        current_structure='STRUCTURE_BULL',support_zone_low=price-4,support_zone_high=price-2,
        resistance_zone_low=price+2,resistance_zone_high=price+3,nearest_swing_high=price+5,
        protected_high=price+8,atr_ma_ratio=1) for r in rows])
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1500,'height':1000});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && !DataCache.loading && !DataCache._olderPromise')
        await page.wait_for_function("DataCache.bars.at(-1)?.confidence?.status==='ready'")
        points=await page.evaluate("import('/overlays/candles/index.js').then(m=>m.getSeries().data().map(({time,open,high,low,close})=>({time,open,high,low,close})))")
        assert 'scores, not probabilities' in await page.locator('.evidence-status').inner_text()
        await page.get_by_role('button',name='Open settings',exact=True).click()
        dialog=page.get_by_role('dialog',name='Settings',exact=True)
        await dialog.get_by_role('tab',name='Features',exact=True).click()
        await dialog.get_by_role('button',name='Confidence',exact=True).click()
        await dialog.get_by_role('button',name='Data',exact=True).click()
        assert 'momentum' in await dialog.inner_text()
        await dialog.get_by_role('button',name='Opportunity',exact=True).click()
        await dialog.get_by_role('button',name='Display',exact=True).click()
        await dialog.get_by_role('button',name='Select all',exact=True).click()
        await dialog.get_by_role('button',name='Style',exact=True).click()
        await dialog.get_by_label('Fee per side (bps)',exact=True).fill('8')
        await dialog.get_by_label('Slippage per side (bps)',exact=True).fill('3')
        await dialog.get_by_role('button',name='Apply',exact=True).click();await settle(page)
        await page.wait_for_function('DataCache.bars.at(-1)?.opportunity?.costs.round_trip_bps===22')
        assert await page.evaluate("import('/overlays/opportunity/index.js').then(m=>m.targetRows(DataCache.bars.at(-1),Composer.config.featureStyles).filter(r=>r.side==='buy').length)")==3
        assert await page.evaluate("import('/overlays/candles/index.js').then(m=>m.getSeries().data().map(({time,open,high,low,close})=>({time,open,high,low,close})))")==points
        assert 'assumed round-trip 22 bps' in await page.locator('.evidence-status').inner_text()
        await page.screenshot(path='/tmp/tradingbot-evidence.png')
        await page.reload();await sign_in(page,'user');await page.wait_for_function('window.Composer?.mounted && !DataCache.loading')
        assert await page.evaluate('Composer.config.featureStyles.opportunity_buy_1.feeBps')==8
        assert not errors,errors
        await browser.close()
        print('PASS: confidence breakdown, three targets, editable costs, unchanged candles and persisted settings')

if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
