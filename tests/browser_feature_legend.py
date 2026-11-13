"""Feature legend controls real overlays/panes and persists browser preferences."""
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in,settle

async def exercise(base,library):
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1500,'height':1000})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user')
        await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length===2000 && !DataCache._olderPromise')
        await page.evaluate('''async()=>{
            const {migrateStyles}=await import('/controls/settings/feature_styles.js');
            const outputs=migrateStyles();for(const output of Object.values(outputs))output.visible=false;
            for(const key of ['ema7','ema50','wma50','rsi','bull_fvg_zones'])outputs[key].visible=true;
            outputs.rsi.color='#123abc';
            localStorage.setItem('tradingbot.chart-settings.v1',JSON.stringify({outputs,ema:true,markers:true}));
        }''')
        await page.reload();await sign_in(page,'user')
        try:
            await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length>=2000 && !DataCache._olderPromise')
        except Exception:
            print(await page.evaluate('({mounted:window.Composer?.mounted,bars:window.DataCache?.bars?.length,status:document.getElementById("status")?.textContent})'),errors,flush=True)
            raise
        legend=page.get_by_role('region',name='Chart features',exact=True)
        assert sorted(await legend.locator('.feature-legend-name').all_text_contents())==['EMA','FVG','RSI','WMA']
        await page.get_by_role('group',name='RSI pane controls',exact=True).wait_for()
        await legend.get_by_role('button',name='Hide RSI on chart',exact=True).click();await settle(page)
        assert await page.get_by_role('group',name='RSI pane controls',exact=True).count()==0
        await legend.get_by_role('button',name='Show RSI on chart',exact=True).wait_for()
        await page.reload();await sign_in(page,'user')
        try:
            await page.wait_for_function('window.Composer?.mounted && DataCache.bars.length>=2000 && !DataCache._olderPromise')
        except Exception:
            print(await page.evaluate('({mounted:window.Composer?.mounted,bars:window.DataCache?.bars?.length,status:document.getElementById("status")?.textContent})'),errors,flush=True)
            raise
        await legend.get_by_role('button',name='Show RSI on chart',exact=True).click();await settle(page)
        await page.get_by_role('group',name='RSI pane controls',exact=True).wait_for()
        assert await page.evaluate("Composer.config.featureStyles.rsi.color")=='#123abc'
        await legend.get_by_role('button',name='Hide EMA on chart',exact=True).click();await settle(page)
        assert await page.evaluate("Composer.config.ema.periods.length")==0
        await legend.get_by_role('button',name='Show EMA on chart',exact=True).click();await settle(page)
        assert await page.evaluate("Composer.config.ema.periods")==[7,50]
        await legend.get_by_role('button',name='Remove WMA from chart',exact=True).click();await settle(page)
        assert await legend.locator('[data-feature="WMA"]').count()==0
        assert await page.evaluate("Composer.config.featureStyles.wma50.visible") is False
        await legend.get_by_role('button',name='FVG feature settings',exact=True).click()
        settings=page.get_by_role('dialog',name='Settings',exact=True)
        await settings.get_by_role('button',name='WMA',exact=True).click()
        await settings.get_by_label('WMA 50',exact=True).check()
        await settings.get_by_role('button',name='Apply',exact=True).click();await settle(page)
        await legend.get_by_role('button',name='Hide WMA on chart',exact=True).wait_for()
        layout=await legend.evaluate('node=>({left:parseFloat(getComputedStyle(node).left),gap:getComputedStyle(node).gap,rows:[...node.children].map(row=>({height:row.getBoundingClientRect().height,background:getComputedStyle(row).backgroundColor}))})')
        assert layout['left']==12 and layout['gap']=='0px',layout
        assert all(row['height']<=20 and row['background']=='rgba(0, 0, 0, 0)' for row in layout['rows']),layout
        await page.wait_for_function('''()=>{const legend=document.getElementById('feature-legend'),hud=document.querySelector('.chart-hud');return !hud||hud.hidden||hud.dataset.position!=='top-left'||hud.getBoundingClientRect().top>=legend.getBoundingClientRect().bottom;}''')
        await page.screenshot(path='/tmp/tradingbot-feature-legend-desktop.png')
        await page.set_viewport_size({'width':420,'height':850});await settle(page)
        bounds=await legend.bounding_box();assert bounds and bounds['x']>=0 and bounds['x']+bounds['width']<=420
        await legend.get_by_role('button',name='Hide FVG on chart',exact=True).click();await settle(page)
        assert await page.evaluate("Composer.config.featureStyles.bull_fvg_zones.visible") is False
        await page.screenshot(path='/tmp/tradingbot-feature-legend.png')
        assert not errors,errors
        await browser.close()
        print('PASS: all catalog families, hide/show panes and overlays, exact EMA restoration, remove/re-enable, persistence and mobile layout',flush=True)

if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
