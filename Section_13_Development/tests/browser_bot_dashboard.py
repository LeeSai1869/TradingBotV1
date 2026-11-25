"""Independent dashboard in Chromium: config, concurrent edits, fills, close and mobile."""
import asyncio
from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import patch
from playwright.async_api import async_playwright,expect
from Section_15_Execution_Bot.config import Config
from Section_15_Execution_Bot.engine import Ledger
from Section_15_Execution_Bot.quotes import Quote
from Section_15_Execution_Bot.dashboard import Server
from Section_15_Execution_Bot import source


async def exercise(base,ledger):
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1440,'height':1100});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(base)
        await page.get_by_role('heading',name='ENAUSDT / 5m',exact=True).wait_for()
        assert await page.locator('#cash').inner_text()=='100'
        assert await page.get_by_role('button',name='Edit settings',exact=True).is_disabled()
        await page.get_by_role('button',name='Pause entries',exact=True).click()
        await page.get_by_role('button',name='Edit settings',exact=True).wait_for(state='visible')
        await expect(page.locator('#settings')).to_be_enabled()
        await page.get_by_role('button',name='Edit settings',exact=True).click()
        dialog=page.get_by_role('dialog',name='Edit allocation settings',exact=True)
        await dialog.get_by_label('Stop-loss (%)',exact=True).fill('3')
        await dialog.get_by_label('Maximum per entry (USDT)',exact=True).fill('50')
        await dialog.get_by_role('button',name='Save settings',exact=True).click()
        await dialog.wait_for(state='hidden')
        assert ledger.view('ena-5m')['accounts'][0]['config']['capital_cap']=='50'
        assert ledger.view('ena-5m')['accounts'][0]['state']['cash']=='100'
        # A stale tab cannot overwrite an independently saved configuration.
        await page.get_by_role('button',name='Edit settings',exact=True).click()
        current=ledger.view()['accounts'][0]
        ledger.configure('ena-5m',{'fee_bps':'11'},int(time.time()*1000),expected_config=current['config_token'])
        await dialog.get_by_label('Take-profit (%)',exact=True).fill('5')
        await dialog.get_by_role('button',name='Save settings',exact=True).click()
        await expect(page.locator('#form-error')).to_contain_text('Configuration changed')
        await dialog.get_by_role('button',name='Cancel',exact=True).click()
        await page.get_by_role('button',name='Refresh',exact=True).click()
        await page.get_by_role('button',name='Resume entries',exact=True).click()
        await expect(page.locator('#state-badge')).to_have_text('ENTRIES ENABLED')
        now=int(time.time()*1000)
        ledger.step('ena-5m',Quote('ENAUSDT','1','1.001',now),dict(epoch='fixture',events=[dict(open_time=now-1000,close_time=now-1,side='BUY')]),now)
        await page.get_by_role('button',name='Refresh',exact=True).click()
        await expect(page.locator('#close-position')).to_be_enabled()
        assert await page.get_by_role('button',name='Edit settings',exact=True).is_disabled()
        await page.get_by_role('button',name='Close paper position',exact=True).click()
        close=page.get_by_role('dialog',name='Close paper position',exact=True)
        await close.get_by_role('button',name='Close & pause entries',exact=True).click()
        await close.wait_for(state='hidden')
        await expect(page.locator('#position')).to_have_text('No open position')
        assert await page.get_by_role('cell',name='Manual paper exit',exact=True).count()==1
        state=ledger.view('ena-5m')['accounts'][0]['state']
        assert state['quantity']=='0' and not state['enabled']
        await page.get_by_role('button',name='New allocation',exact=True).click()
        new=page.get_by_role('dialog',name='New paper allocation',exact=True)
        await new.get_by_label('Allocation name',exact=True).fill('eth-15m')
        await new.get_by_label('Coin',exact=True).fill('ETHUSDT')
        await new.get_by_label('Strategy timeframe',exact=True).select_option('15m')
        await new.get_by_role('button',name='Create paused allocation',exact=True).click()
        await new.wait_for(state='hidden')
        await page.get_by_role('heading',name='ETHUSDT / 15m',exact=True).wait_for()
        assert await page.locator('#state-badge').inner_text()=='ENTRIES PAUSED'
        assert await page.locator('#fills').inner_text()=='No paper executions yet. New confirmed signals will appear here.'
        await page.get_by_role('button',name='ENAUSDT · 5m ena-5m · Paused',exact=True).click()
        await page.get_by_role('heading',name='ENAUSDT / 5m',exact=True).wait_for()
        await page.get_by_role('cell',name='Manual paper exit',exact=True).wait_for()
        await page.screenshot(path='/tmp/paper-bot-dashboard-desktop.png',full_page=True)
        await page.set_viewport_size({'width':390,'height':844})
        await page.screenshot(path='/tmp/paper-bot-dashboard-mobile.png',full_page=True)
        assert (await page.locator('body').bounding_box())['width']<=390
        assert not errors,errors
        print('PASS: independent dashboard, pause/resume, safe config edits, stale-edit rejection, paper close, isolated history, allocation creation and mobile layout')
        await browser.close()


def main():
    with tempfile.TemporaryDirectory() as directory:
        ledger=Ledger(Path(directory)/'bot.db');now=int(time.time()*1000)
        cfg=source.bind_current(Config('ena-5m','ENAUSDT','5m','current','100','200','2','4',strategy_source='current'))
        ledger.create(cfg,now);ledger.enabled(cfg.name,True,now)
        ledger.step(cfg.name,Quote('ENAUSDT','1','1.001',now),dict(epoch='fixture',events=[]),now)
        pipeline=dict(raw_open_ms=now-300000,raw_close_ms=now-1,raw_age_seconds=0,feature_through_ms=now-300000,
            decision_through_ms=now-300000,decision_lag_seconds=0,raw_stale=False,latest_signal_last_24h=None)
        with patch.object(source,'snapshot',return_value=dict(epoch='fixture',events=[])),patch.object(source,'health',return_value=pipeline),\
             patch('Section_15_Execution_Bot.quotes.fetch',side_effect=lambda symbol:Quote(symbol,'1.1','1.101',int(time.time()*1000))) as fetch:
            server=Server(ledger.path,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:asyncio.run(exercise(f'http://127.0.0.1:{server.server_port}',ledger));assert fetch.call_count==1
            finally:server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':main()
