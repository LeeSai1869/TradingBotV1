"""Real chart/settings integration with disposable observed-depth fixtures; no exchange I/O."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in,settle,db
from Section_1_Global_Core.liquidity import store
from Section_1_Global_Core.liquidity.book import Book
from Section_11_UI_UX.server import liquidity


async def exercise(base,library):
    row=db.read_last_klines('BTCUSDT','15m',1)[0];now=row[8]-2000;price=row[6]
    book=Book('BTCUSDT')
    book.snapshot(dict(lastUpdateId=10,bids=[[str(price-.1),'20'],[str(price-10),'1']],asks=[[str(price+.1),'30'],[str(price+10),'1']]))
    book.apply(dict(s='BTCUSDT',U=10,u=11,pu=9,E=now,T=now,b=[],a=[]),now)
    packet=book.features(now)
    with tempfile.TemporaryDirectory() as directory,patch.object(store,'DB_PATH',Path(directory)/'liquidity.db'),patch.object(liquidity,'snapshot',side_effect=lambda symbol:store.snapshot(symbol,now_ms=now)):
        conn=store.open_writer()
        with conn:
            for i in range(30):
                stamp=now-(29-i)*5000
                store.write_sample(conn,{**packet,'available_ms':stamp,'book_received_ms':stamp,'exchange_ms':stamp},stamp)
        conn.close()
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=await browser.new_page(viewport={'width':1500,'height':1000});errors=[];requests=[]
            page.on('pageerror',lambda error:errors.append(str(error)));page.on('request',lambda req:requests.append(req.url))
            await page.add_init_script(f'Date.now=()=>{now};')
            await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
            await page.goto(base);await sign_in(page,'user')
            await page.wait_for_function('window.Composer?.mounted && !DataCache.loading && !DataCache._olderPromise')
            await page.get_by_role('button',name='Open settings',exact=True).click()
            dialog=page.get_by_role('dialog',name='Settings',exact=True)
            await dialog.get_by_role('tab',name='Features',exact=True).click()
            await dialog.get_by_role('button',name='Liquidity',exact=True).click()
            await dialog.get_by_role('button',name='Select all',exact=True).click()
            assert await dialog.get_by_label('Observed depth heatmap color',exact=True).is_disabled()
            await dialog.get_by_label('Resting perpetual bids bar opacity',exact=True).fill('45')
            await dialog.get_by_role('button',name='Apply',exact=True).click();await settle(page)
            await page.wait_for_function("DataCache.liquidity?.status==='live'")
            assert 'observed orders (USDT)' in await page.locator('.liquidity-status').inner_text()
            assert 'spot candles' in await page.locator('.liquidity-status').inner_text()
            assert await page.evaluate('DataCache.liquidity.history.length')==30
            assert await page.evaluate('Composer.config.featureStyles.liquidity_bids.opacity')==45
            assert any('liquidity=1' in url and '/api/bars?' in url for url in requests)
            assert not any('/api/liquidity' in url for url in requests)
            await page.screenshot(path='/tmp/tradingbot-liquidity.png')
            with patch.object(liquidity,'snapshot',return_value=dict(status='stale',reason='sequence gap',latest=None,history=[packet])):
                await page.evaluate('DataCache.refreshStored()');await settle(page)
                assert 'stale' in await page.locator('.liquidity-status').inner_text()
                assert await page.evaluate("import('/overlays/liquidity/index.js').then(m=>m.fresh(m.getSnapshot()))") is None
            await page.reload();await sign_in(page,'user');await page.wait_for_function('window.Composer?.mounted && !DataCache.loading')
            assert await page.evaluate('Composer.config.featureStyles.liquidity_bids.opacity')==45
            assert not errors,errors
            print('PASS: observed perpetual bands and heatmap, combined poll, market labels, settings persistence and stale hiding',flush=True)
            await browser.close()

if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
