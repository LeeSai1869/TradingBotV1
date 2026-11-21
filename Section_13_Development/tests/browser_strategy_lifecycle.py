"""Signed-in configurable strategies, selected-only markers and scoped deletion."""
from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from unittest.mock import patch
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in,settle,db,features_store,klines_store
from Section_8_Decision_Engine import processor,strategy_registry as registry
from Section_1_Global_Core.memory_storage.Storage import adcn_store


async def exercise(base,library):
    with klines_store.open_db() as conn:rows=conn.execute("SELECT open_time,close_time FROM klines WHERE symbol='BTCUSDT' AND interval='15m' ORDER BY open_time DESC LIMIT 3").fetchall()[::-1]
    measurements=[(10,30,20,99),(11,35,21,100),(15,27,22,101)]
    raw=[];features=[]
    for (stamp,closed),(plus,minus,adx,price) in zip(rows,measurements):
        raw.append(dict(symbol='BTCUSDT',interval='15m',open_time=stamp,close_time=closed,open=price,high=price+1,low=price-1,close=price,volume=10))
        features.append(dict(symbol='BTCUSDT',interval='15m',open_time=stamp,formula_version=3,di_plus=plus,di_minus=minus,di_spread=abs(plus-minus),adx=adx,ema50=100,atr=1))
    db.write_klines(raw);db.write_features(features)
    with features_store.open_db() as conn:conn.execute("INSERT OR REPLACE INTO feature_engine_state VALUES ('BTCUSDT','15m',?,'{}')",(rows[-1][0],))
    original=registry.require('di_turning_point',3)
    def evaluate(previous,current):
        result=original.module.evaluate(previous,current)
        if result['signal_type']:
            side='SELL' if result['signal_type']=='BUY' else 'BUY';return dict(signal_type=side,decision_state=side,trigger='TEST_VERSION_4')
        return result
    fake=replace(original,version=4,name='Fixture reverse v4',module=SimpleNamespace(FIELDS=original.module.FIELDS,LOOKBACK=2,evaluate=evaluate),fingerprint='test-version-4')
    with patch.dict(registry.DEFINITIONS,{('di_turning_point',4):fake}):
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=await browser.new_page(viewport={'width':1500,'height':1000});errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            await page.route('https://unpkg.com/**',lambda route:route.fulfill(path=str(library),content_type='application/javascript'))
            await page.goto(base);await sign_in(page)
            await page.wait_for_function('window.DataCache&&!DataCache.loading&&DataCache.bars.length===2000')
            await page.get_by_role('button',name='Open settings',exact=True).click()
            dialog=page.get_by_role('dialog',name='Settings')
            await dialog.get_by_role('tab',name='Features',exact=True).click()
            await dialog.get_by_role('button',name='Strategies',exact=True).click()
            await dialog.get_by_label('Strategy coin',exact=True).select_option('BTCUSDT')
            await dialog.get_by_label('Strategy timeframe',exact=True).select_option('15m')
            date=datetime.fromtimestamp(rows[0][0]/1000,timezone.utc).strftime('%Y-%m-%dT%H:%M')
            await dialog.get_by_label('Strategy history start',exact=True).fill(date)
            await dialog.get_by_role('button',name='Enable and select strategy',exact=True).click()
            await dialog.locator('legend',has_text='v3 · Selected').wait_for()
            processor.catch_up('BTCUSDT','15m')
            await page.wait_for_function('!DataCache.loading&&!DataCache._olderPromise')
            await page.evaluate('async()=>{await DataCache._refreshPromise;return DataCache.refreshStored({full:true});}')
            await page.wait_for_function('DataCache.latestBar?.adcn?.strategy_version===3')
            await dialog.get_by_label('Production strategy',exact=True).select_option('di_turning_point:4')
            await dialog.get_by_label('Strategy history start',exact=True).fill(date)
            await dialog.get_by_role('button',name='Enable and select strategy',exact=True).click()
            await dialog.locator('legend',has_text='v4 · Selected').wait_for()
            processor.catch_up('BTCUSDT','15m')
            await page.wait_for_function('!DataCache.loading&&!DataCache._olderPromise')
            await page.evaluate('async()=>{await DataCache._refreshPromise;return DataCache.refreshStored({full:true});}')
            await page.wait_for_function("DataCache.latestBar?.adcn?.strategy_version===4&&DataCache.latestBar?.momentum?.signal_type==='SELL'")
            group=dialog.locator('fieldset').filter(has_text='di_turning_point v4 · Selected')
            await group.get_by_role('button',name='Deactivate',exact=True).click()
            await dialog.locator('legend',has_text='v4 · Inactive').wait_for()
            await page.wait_for_function('!DataCache.loading&&DataCache.latestBar?.strategy_managed&&!DataCache.latestBar?.momentum')
            group=dialog.locator('fieldset').filter(has_text='di_turning_point v4 · Inactive')
            await group.get_by_role('button',name='Preview strategy deletion',exact=True).click()
            await group.locator('pre').filter(has_text='Type: DELETE').wait_for()
            text=await group.locator('pre').text_content();confirmation=re.search(r'Type: (DELETE \w+)',text).group(1)
            await group.get_by_label('Strategy deletion confirmation',exact=True).fill(confirmation)
            await group.get_by_role('button',name='Delete this strategy and its memory',exact=True).click()
            await dialog.locator('legend',has_text='v4').wait_for(state='detached')
            remaining=dialog.locator('fieldset').filter(has_text='di_turning_point v3 · Comparison')
            await remaining.get_by_role('button',name='Select for chart',exact=True).click()
            await page.wait_for_function("DataCache.latestBar?.adcn?.strategy_version===3&&DataCache.latestBar?.momentum?.signal_type==='BUY'")
            with adcn_store.open_db() as conn:
                assert conn.execute('SELECT version FROM strategy_instances').fetchall()==[(3,)]
                assert conn.execute('SELECT COUNT(*) FROM strategy_events').fetchone()[0]==1
            assert not errors,errors
            print('PASS: configurable pair, strategy enable/switch, selected-only markers, deactivate, scoped preview/delete and preserved comparison history')
            await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),scenario=exercise)
