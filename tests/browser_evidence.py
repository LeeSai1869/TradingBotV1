"""Disposable closed-feature scenarios, real chart; no exchange or order calls."""
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in,settle,db,klines_store


async def exercise(base,library):
    rows=db.read_last_klines('BTCUSDT','15m',100);price=rows[-1][6]
    db.write_features([dict(symbol='BTCUSDT',interval='15m',open_time=r[2],formula_version=3,
        atr=2,ema50=price-2,ema200=price-5,vwap=price-1,rsi=65,di_plus=30,di_minus=10,di_spread=20,adx=32,
        current_structure='STRUCTURE_BULL',support_zone_low=price-2.5,support_zone_high=price-2,
        resistance_zone_low=price+2,resistance_zone_high=price+2.5,nearest_swing_high=price+5,
        protected_high=price+8,atr_ma_ratio=1,inst_resistance_zone_low=price+12,inst_resistance_zone_high=price+12.5,
        nearest_bear_fvg_low=price+22,nearest_bear_fvg_high=price+22.5,inst_support_zone_low=price-13.5,inst_support_zone_high=price-13,
        nearest_bull_fvg_low=price-23.5,nearest_bull_fvg_high=price-23) for r in rows])
    # Canonical three-candle SELL gate, with a rejection candle at the anchor.
    closes=[price-2,price,price-1];pulse=rows[-10:-7]
    for index,r in enumerate(pulse):
        c=closes[index]
        db.write_features([dict(symbol='BTCUSDT',interval='15m',open_time=r[2],formula_version=3,
            atr=2,ema50=price-2,ema200=price-5,vwap=price-1,rsi=88 if index==1 else 80,
            di_plus=[30,35,27][index],di_minus=[10,11,15][index],di_spread=[20,24,12][index],adx=20+index,
            current_structure='STRUCTURE_BULL',support_zone_low=price-2.5,support_zone_high=price-2,
            resistance_zone_low=price+2,resistance_zone_high=price+2.5,nearest_swing_high=price+5,protected_high=price+8,atr_ma_ratio=1,inst_resistance_zone_low=price+12,inst_resistance_zone_high=price+12.5,
        nearest_bear_fvg_low=price+22,nearest_bear_fvg_high=price+22.5,inst_support_zone_low=price-13.5,inst_support_zone_high=price-13,
        nearest_bull_fvg_low=price-23.5,nearest_bull_fvg_high=price-23)])
    conn=klines_store.open_db()
    with conn:
        for index,r in enumerate(pulse):
            c=closes[index]
            opened,high,low=(price+1,price+3,price-1.5) if index==2 else (c+.1,c+1,c-1)
            conn.execute('UPDATE klines SET open=?,high=?,low=?,close=? WHERE symbol=? AND interval=? AND open_time=?',
                (opened,high,low,c,'BTCUSDT','15m',r[2]))
    conn.close()
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
        await dialog.get_by_role('button',name='Data',exact=True).click()
        assert 'Source timeframe: 15m' in await dialog.inner_text()
        assert await dialog.get_by_text('Sources and area selection',exact=True).count()==1
        await dialog.get_by_role('button',name='Display',exact=True).click()
        await dialog.get_by_role('button',name='Select all',exact=True).click()
        await dialog.get_by_role('button',name='Apply',exact=True).click();await settle(page)
        assert await page.evaluate("time=>DataCache.bars.find(b=>b.open_time===time).momentum.signal_type",pulse[-1][2])=='SELL'
        assert await page.evaluate('DataCache.bars.at(-1).signal_context.entry')==price-1
        anchored=await page.evaluate("import('/overlays/opportunity/index.js').then(m=>m.targetRows(DataCache.bars.at(-1),Composer.config.featureStyles))")
        assert len(anchored)==6
        assert all(row['high']<price-1 for row in anchored if row['role']=='support')
        assert all(row['low']>price-1 for row in anchored if row['role']=='resistance')
        assert all(row['net_high']<0 for row in anchored if row['role']=='resistance')
        assert await page.evaluate('DataCache.bars.at(-1).signal_context.confidence.sell_mode')=='reversal'
        await page.get_by_role('button',name='Open settings',exact=True).click()
        await dialog.get_by_role('button',name='Opportunity',exact=True).click()
        assert await dialog.get_by_role('checkbox',name='Preview both directions from the latest close (unanchored)',exact=True).count()==0
        await dialog.get_by_role('button',name='Style',exact=True).click()
        await dialog.get_by_label('Fee per side (bps)',exact=True).fill('8')
        await dialog.get_by_label('Slippage per side (bps)',exact=True).fill('3')
        await dialog.get_by_role('button',name='Apply',exact=True).click();await settle(page)
        await page.wait_for_function('DataCache.bars.at(-1)?.opportunity?.costs.round_trip_bps===22')
        await page.evaluate('DataCache._refreshCount=0; DataCache.refreshStored()');await settle(page)
        assert await page.evaluate('DataCache.bars.at(-1).signal_context.open_time')==pulse[-1][2]
        projected=await page.evaluate("import('/overlays/opportunity/index.js').then(m=>m.targetRows(DataCache.bars.at(-1),Composer.config.featureStyles))")
        assert len(projected)==6 and all(row['high']>row['low'] and row['entry']==price-1 for row in projected)
        assert await page.evaluate('DataCache.bars.at(-1).opportunity.entry')==price-1
        assert await page.evaluate("import('/overlays/candles/index.js').then(m=>m.getSeries().data().map(({time,open,high,low,close})=>({time,open,high,low,close})))")==points
        assert await page.evaluate('DataCache.bars.at(-1).signal_context.costs.round_trip_bps')==22
        assert 'opportunity bands' in await page.locator('.evidence-status').inner_text()
        await page.screenshot(path='/tmp/tradingbot-evidence.png')
        await page.reload();await sign_in(page,'user');await page.wait_for_function('window.Composer?.mounted && !DataCache.loading')
        assert await page.evaluate('Composer.config.featureStyles.opportunity_buy_1.feeBps')==8
        assert not errors,errors
        await browser.close()
        print('PASS: independent reversal score, SELL anchor and six frozen areas, merged bands, two-candle refresh, costs, unchanged candles and persistence')

if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
