"""Actual chart: protected references, confirmed lines, range band and settings."""
import asyncio
import json
from pathlib import Path
import sys
from playwright.async_api import async_playwright,expect
from browser_smoke import run,sign_in,settle,db


async def exercise(base,library):
    rows=db.read_last_klines('BTCUSDT','15m',220);price=rows[-1][6]
    features=[]
    for i,r in enumerate(rows):
        events=[]
        if i>=1 and i%25==1:
            origin=rows[i-1];high=(i//25)%2==0
            events=[dict(type='PIVOT_HIGH' if high else 'PIVOT_LOW',origin_time=origin[2],confirmation_time=r[2],price=origin[4] if high else origin[5])]
        features.append(dict(symbol='BTCUSDT',interval='15m',open_time=r[2],ema50=r[6]-.5,
            protected_high=price*.7,protected_low=price*.6,protected_high_bar=1,protected_low_bar=0,
            current_structure='STRUCTURE_RANGE',structure_range_low=price-2,structure_range_high=price+2,structure_origin_bar=1,
            structure_events=json.dumps(events),structure_events_version='structure-events-v1',structure_event_status='READY'))
    db.write_features(features)
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1500,'height':950});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.add_init_script("""(()=>{const original=CanvasRenderingContext2D.prototype.fillText;window.__structureLabels=[];CanvasRenderingContext2D.prototype.fillText=function(t,...args){if(/^(PH|PL) /.test(String(t)))window.__structureLabels.push(String(t));return original.call(this,t,...args);};})();""")
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000 && !DataCache._olderPromise')
        await page.evaluate("window.dispatchEvent(new CustomEvent('open-feature-settings',{detail:'Market Structure'}))")
        dialog=page.get_by_role('dialog',name='Settings',exact=True)
        await dialog.get_by_role('button',name='Display',exact=True).click()
        for label in ['Protected high (PH)','Protected low (PL)','Confirmed-high trend line','Confirmed-low trend line','Established range band','Swing high (SH)','Swing low (SL)']:
            await dialog.get_by_label(label,exact=True).check()
        await dialog.get_by_role('button',name='Apply',exact=True).click();await settle(page)
        geometry=await page.evaluate("async()=>{const m=await import('/overlays/structure_tags/index.js');return m.structureGeometry(DataCache.renderBars,Composer.config.featureStyles);}")
        assert len(geometry['protectedLevels'])==2
        assert len(geometry['trendLines'])==2 and all(len(line['points'])>=2 for line in geometry['trendLines'])
        await page.wait_for_function("window.__structureLabels.some(t=>t.startsWith('PH '))&&window.__structureLabels.some(t=>t.startsWith('PL '))")
        assert any('↓' in t for t in await page.evaluate('window.__structureLabels'))
        segments=await page.evaluate("async()=>(await import('/overlays/zones/index.js')).getSegments()")
        assert any(s['key']=='structure_range_zones' for s in segments)
        await page.screenshot(path='/tmp/structure-overlays-desktop.png',full_page=True)
        # Changing market must discard the prior market's references/lines.
        await page.get_by_role('button',name='Choose symbol',exact=True).click()
        await page.get_by_role('combobox',name='Search symbol',exact=True).fill('SUIUSDT')
        await page.get_by_role('option',name='SUIUSDT · Sui',exact=True).click()
        await page.wait_for_function("DataCache.symbol==='SUIUSDT'&&!DataCache.loading");await settle(page)
        geometry=await page.evaluate("async()=>{const m=await import('/overlays/structure_tags/index.js');return m.structureGeometry(DataCache.renderBars,Composer.config.featureStyles);}")
        assert not geometry['protectedLevels']
        assert all(not line['points'] for line in geometry['trendLines'])
        assert not errors,errors
        print('PASS: real chart PH/PL edge prices, two confirmed trend lines, actual range band, settings, and no cross-market leakage')
        await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
