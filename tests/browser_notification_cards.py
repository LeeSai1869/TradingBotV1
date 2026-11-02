"""Dismissible rich alert, exact historical chart navigation and mobile shell."""
from pathlib import Path
import json
import sys
import time
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in
from Section_11_UI_UX.server import alerts

async def exercise(base,library):
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1500,'height':1000});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
        await page.goto(base);await sign_in(page,'user');await page.wait_for_function('typeof openAlertChart === "function" && !DataCache.loading')
        t=1781654400000-2100*60000
        event=dict(name='BUY',symbol='SUIUSDT',interval='1m',bar_time=t,created=int(time.time()*1000),field='decision.buy',sound='none',notify=False,
            message='SUI historical BUY',details={'side':'BUY','price':101,'confidence':88,'upper':{'low':105,'high':106},'lower':{'low':94,'high':95}})
        conn=alerts.open_db()
        with conn:conn.execute('INSERT INTO events(owner,rule_id,epoch,bar_time,created,packet) VALUES (?,?,?,?,?,?)',('user','card-test','0',t,event['created'],json.dumps(event)))
        conn.close()
        card=page.locator('#alert-toasts .alert-toast').filter(has_text='SUIUSDT 1m BUY');await card.wait_for()
        assert '88/100' in await card.inner_text();assert '106' in await card.inner_text();assert '94' in await card.inner_text()
        await card.get_by_role('link').click();await page.wait_for_function("DataCache.symbol==='SUIUSDT'&&DataCache.timeframe==='1m'&&!DataCache.loading")
        await page.wait_for_function('at=>{const bars=DataCache.renderBars,i=bars.findIndex(b=>b.open_time===at),r=Canvas.chart.timeScale().getVisibleLogicalRange();return i>=0&&r&&r.from<=i&&i<=r.to;}',arg=t)
        assert f'at={t}' in page.url
        await card.get_by_role('button',name='Dismiss notification').click();await card.wait_for(state='detached')
        await page.get_by_role('button',name='Go to latest candle',exact=True).click()
        await page.wait_for_function('!DataCache.loading && DataCache.latestBar?.open_time===1781654400000-60000')
        assert 'at=' not in page.url
        mobile=await browser.new_page();await mobile.goto(base+'/web_root/mobile.html')
        await mobile.clock.install();await mobile.evaluate("async()=>{const m=await import('/web_root/notification_view.js');document.body.append(m.notificationCard({name:'Test',symbol:'BTCUSDT',interval:'1m',bar_time:0,created:Date.now()},{ephemeral:true}));}")
        assert await mobile.locator('.alert-toast').count()==1
        await mobile.clock.fast_forward(20001);assert await mobile.locator('.alert-toast').count()==0
        await mobile.get_by_label('Username',exact=True).fill('user');await mobile.get_by_label('Password',exact=True).fill('test-password-long');await mobile.get_by_role('button',name='Sign in',exact=True).click()
        await mobile.get_by_text('Signed in as user',exact=True).wait_for();assert await mobile.get_by_role('button',name='Enable mobile notifications').is_disabled()
        assert 'HTTPS' in await mobile.locator('#mobile-setup').inner_text()
        assert not errors,errors
        await browser.close();print('PASS: rich card, dismiss, 20s expiry, historical signal chart focus, installable mobile shell and explicit setup-needed state')

if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
