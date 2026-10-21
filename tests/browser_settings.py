"""Settings navigation, persistence and chart behavior on isolated databases.

PYTHONPATH=. python3 tests/browser_settings.py /path/to/lightweight-charts.standalone.production.js
"""
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from browser_smoke import run, settle, sign_in, db


async def exercise_settings(base, library):
    # A second real stored feature proves period selection uses the combined bars.
    t = 1781654400000 - 900000
    db.write_features([dict(symbol='BTCUSDT', interval='15m', open_time=t,
                           ema25=244, ema50=240)])
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width':1500, 'height':1000})
        errors = []; mutations = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: mutations.append(r.url) if r.method != 'GET' and not any(path in r.url for path in ['/api/login','/api/logout']) else None)
        await page.route('https://unpkg.com/**', lambda route: route.fulfill(path=str(library), content_type='application/javascript'))
        async def capture_series(route):
            response = await route.fetch()
            source = await response.text()
            source += """
const originalInit = Canvas.init.bind(Canvas);
Canvas.init = (...args) => {
    const chart = originalInit(...args), add = chart.addSeries.bind(chart);
    window.settingsSeries = [];
    chart.addSeries = (...params) => { const s = add(...params); settingsSeries.push(s); return s; };
    return chart;
};
"""
            await route.fulfill(response=response, body=source)
        await page.route('**/chart/index.js', capture_series)
        await page.goto(base)
        await sign_in(page)
        await page.wait_for_function('window.DataCache && DataCache.bars.length===2000 && !DataCache._olderPromise')
        await settle(page)
        await page.evaluate('''() => {
            window.emaWrites=[];
            for (const s of settingsSeries) {
                const original=s.setData.bind(s);
                s.setData=(points)=>{ if(points.some(p=>p.value===244)) emaWrites.push(points); return original(points); };
            }
            Canvas.chart.timeScale().setVisibleLogicalRange({from:700,to:1699});
        }''')
        await settle(page)
        before = await page.evaluate('Canvas.chart.timeScale().getVisibleLogicalRange()')
        await page.get_by_role('button', name='Open settings').click()
        dialog = page.get_by_role('dialog', name='Settings')
        await dialog.get_by_role('switch', name='Show BUY / SELL markers').uncheck()
        await dialog.get_by_role('button', name='Cancel', exact=True).click()
        assert await page.evaluate('Composer.config.display.markers') is True
        await page.get_by_role('button', name='Open settings').click()
        await dialog.get_by_role('tab', name='Features', exact=True).click()
        await dialog.get_by_label('EMA 25', exact=True).check()
        await dialog.get_by_label('EMA 25 width', exact=True).select_option('3')
        await dialog.get_by_label('EMA 25 line style', exact=True).select_option('2')
        await dialog.get_by_label('EMA 25 color', exact=True).fill('#ff1234')
        await dialog.get_by_role('button', name='RSI', exact=True).click()
        await dialog.get_by_label('RSI width', exact=True).select_option('4')
        await dialog.get_by_label('RSI color', exact=True).fill('#1234ff')
        await dialog.get_by_role('button', name='ADX', exact=True).click()
        assert await dialog.get_by_role('combobox').count() == 2
        await dialog.get_by_role('button', name='DI', exact=True).click()
        await dialog.get_by_label('+DI color', exact=True).fill('#abcdef')
        await dialog.get_by_role('button', name='EMA', exact=True).click()
        await dialog.get_by_role('button', name='Display', exact=True).click()
        assert await dialog.get_by_label('EMA 25', exact=True).is_checked()
        await dialog.get_by_role('button', name='Style', exact=True).click()
        await dialog.get_by_role('button', name='Apply', exact=True).click()
        await settle(page)
        assert await page.evaluate('Composer.config.ema.periods') == [25,50]
        assert await page.evaluate('Composer.config.featureStyles.ema25.width') == 3
        assert await page.evaluate('Composer.config.featureStyles.ema25.style') == 2
        assert await page.evaluate('emaWrites.length') > 0
        assert await page.evaluate('''() => settingsSeries.some(s =>
            s.data().some(p => p.value === 244) && s.options().visible &&
            s.options().lineWidth === 3 && s.options().lineStyle === 2 && s.options().color === '#ff1234')''')
        assert await page.evaluate('Composer.config.featureStyles.ema25.color') == '#ff1234'
        assert await page.evaluate('Composer.config.featureStyles.ema50.width') == 2
        assert await page.evaluate('Composer.config.featureStyles.rsi.width') == 4
        assert await page.evaluate('Composer.config.featureStyles.di_plus.color') == '#abcdef'
        assert not await page.locator('#flags-panel').is_visible()
        assert await page.evaluate('Canvas.chart.timeScale().getVisibleLogicalRange()') == before
        await page.reload()
        await sign_in(page)
        await page.wait_for_function('window.DataCache && DataCache.bars.length>=1500')
        assert await page.evaluate('Composer.config.ema.periods') == [25,50]
        assert not await page.locator('#flags-panel').is_visible()
        await page.get_by_role('button', name='Open settings').click()
        await dialog.get_by_role('tab', name='Coins', exact=True).click()
        await dialog.get_by_text('BTCUSDT', exact=True).wait_for()
        await dialog.get_by_label('Select BTCUSDT', exact=True).check()
        await dialog.get_by_text('1 selected', exact=True).wait_for()
        await dialog.get_by_role('button', name='Ineligible', exact=True).click()
        await dialog.get_by_text('DOGEUSDT', exact=True).wait_for()
        assert await dialog.get_by_role('button', name='Disapprove', exact=True).is_visible()
        await dialog.get_by_role('tab', name='Timeframes', exact=True).click()
        assert await dialog.get_by_label('3m download status', exact=True).is_enabled()
        await page.keyboard.press('Escape')
        assert not await dialog.is_visible()
        assert await page.get_by_role('button', name='Open settings').evaluate('(e)=>e===document.activeElement')
        await page.set_viewport_size({'width':390,'height':844})
        await page.get_by_role('button', name='Open settings').click()
        box = await dialog.bounding_box()
        assert box['x'] >= 0 and box['x'] + box['width'] <= 390
        await dialog.get_by_role('tab', name='Features', exact=True).click()
        await page.set_viewport_size({'width':1500,'height':1000})
        assert not errors, errors
        assert not mutations, mutations
        await browser.close()
        print('PASS: nested settings, Apply/Cancel, stored EMA selection/style, preserved history, browser persistence, registry categories, disabled runner actions, Escape/focus and mobile layout')


if __name__ == '__main__':
    run(Path(sys.argv[1]).resolve(), scenario=exercise_settings)
