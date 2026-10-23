"""Stored support/resistance and FVG displays/styles share canonical bars."""
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in,settle,db


async def exercise(base,library):
    rows=db.read_last_klines('BTCUSDT','15m',150);price=rows[-1][6]
    db.write_features([dict(symbol='BTCUSDT',interval='15m',open_time=r[2],ema50=r[6]-.5,
        support_zone_low=price-4,support_zone_high=price-3,nearest_support_zone_id='s1',
        resistance_zone_low=price+3,resistance_zone_high=price+4,nearest_resistance_zone_id='r1',
        inst_support_zone_low=price-6,inst_support_zone_high=price-5,nearest_inst_support_zone_id='is1',
        inst_resistance_zone_low=price+5,inst_resistance_zone_high=price+6,nearest_inst_resistance_zone_id='ir1',
        nearest_bull_fvg_low=price-2,nearest_bull_fvg_high=price-1,nearest_bull_fvg_created_bar=10,
        nearest_bear_fvg_low=price+1,nearest_bear_fvg_high=price+2,nearest_bear_fvg_created_bar=20,
        vp_poc=price,vp_va_low=price-2,vp_va_high=price+2,vp_hvn_high=price+1,vp_hvn_low=price-1,
        vp_lvn_high=price+4,vp_lvn_low=price-4) for r in rows])
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1500,'height':1000});errors=[];requests=[]
        page.on('pageerror',lambda error:errors.append(str(error)));page.on('request',lambda request:requests.append(request.url))
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000 && !DataCache._olderPromise')
        await page.get_by_role('button',name='Open settings',exact=True).click()
        dialog=page.get_by_role('dialog',name='Settings',exact=True)
        await dialog.get_by_role('tab',name='Features',exact=True).click()
        for name in ('Support / Resistance','FVG','Volume Profile'):
            await dialog.get_by_role('button',name=name,exact=True).click()
            await dialog.get_by_role('button',name='Select all',exact=True).click()
        await dialog.get_by_label('Point of control (POC) color',exact=True).fill('#fedcba')
        await dialog.get_by_label('Point of control (POC) width',exact=True).select_option('4')
        await dialog.get_by_label('Point of control (POC) line style',exact=True).select_option('1')
        await dialog.get_by_label('Value area band fill opacity',exact=True).fill('35')
        await dialog.get_by_role('button',name='Support / Resistance',exact=True).click()
        await dialog.get_by_label('Support zones fill opacity',exact=True).fill('45')
        await dialog.get_by_role('button',name='FVG',exact=True).click()
        await dialog.get_by_label('Bullish FVG color',exact=True).fill('#abcdef')
        await dialog.get_by_label('Bullish FVG width',exact=True).select_option('3')
        await dialog.get_by_label('Bullish FVG line style',exact=True).select_option('2')
        await dialog.get_by_role('button',name='Apply',exact=True).click();await settle(page)
        count=await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().length)")
        assert count==7,count
        assert await page.evaluate("import('/overlays/indicators/index.js').then(x=>x.getSeries('vp_poc').options().color)")=='#fedcba'
        assert await page.evaluate("import('/overlays/indicators/index.js').then(x=>x.getSeries('vp_poc').data().filter(p=>p.value!=null).length)")==150
        assert await page.evaluate('Composer.config.featureStyles.support_zones.opacity')==45
        assert await page.evaluate('Composer.config.featureStyles.bull_fvg_zones.color')=='#abcdef'
        assert await page.evaluate('Canvas.chart.panes().length')==1
        await page.screenshot(path='/tmp/tradingbot-zones.png')
        await page.reload();await sign_in(page,'user');await page.wait_for_function('window.Composer?.mounted && !DataCache.loading')
        assert await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().length)")==7
        await page.get_by_role('button',name='Open settings',exact=True).click()
        await dialog.get_by_role('tab',name='Features',exact=True).click()
        await dialog.get_by_role('button',name='FVG',exact=True).click()
        await dialog.get_by_role('button',name='Deselect all',exact=True).click()
        await dialog.get_by_role('button',name='Apply',exact=True).click();await settle(page)
        assert await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().length)")==5
        assert not any('/api/fvg' in url or '/api/support' in url or '/api/volume_profile' in url for url in requests)
        assert not errors,errors
        print('PASS: S/R and FVG bands, Volume Profile levels/value-area fill, style/opacity persistence, display toggles and combined-stream reuse',flush=True)
        await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
