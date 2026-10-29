"""Stored support/resistance and FVG displays/styles share canonical bars."""
from pathlib import Path
import sys
import json
from playwright.async_api import async_playwright
from browser_smoke import run,sign_in,settle,db,features_store
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution.checkpoint import dump


async def exercise(base,library):
    engine=Engine('BTCUSDT','15m');profiles={}
    for r in db.read_last_klines('BTCUSDT','15m',220):
        b=dict(zip(('symbol','interval','open_time','open','high','low','close','volume','close_time'),r));profiles[r[2]]=engine.step(b)
    conn=features_store.open_db()
    with conn:conn.execute('INSERT OR REPLACE INTO feature_engine_state VALUES (?,?,?,?)',('BTCUSDT','15m',engine.context.last_time,dump(engine,(0,0))))
    conn.close()
    rows=db.read_last_klines('BTCUSDT','15m',150);price=rows[-1][6]
    db.write_features([dict(symbol='BTCUSDT',interval='15m',open_time=r[2],ema50=r[6]-.5,
        support_zone_low=price-4,support_zone_high=price-3,nearest_support_zone_id='s1',
        current_structure='STRUCTURE_RANGE',structure_range_low=price-9,structure_range_high=price-8,structure_origin_bar=1,
        protected_high=price+8,protected_low=price-8,latest_confirmed_pivot_high=price+10,latest_confirmed_pivot_low=price-10,
        resistance_zone_low=price+3,resistance_zone_high=price+4,nearest_resistance_zone_id='r1',
        inst_support_zone_low=price-6,inst_support_zone_high=price-5,nearest_inst_support_zone_id='is1',
        inst_resistance_zone_low=price+5,inst_resistance_zone_high=price+6,nearest_inst_resistance_zone_id='ir1',
        nearest_bull_fvg_low=price-2,nearest_bull_fvg_high=price-1,nearest_bull_fvg_created_bar=10,
        nearest_bear_fvg_low=price+1,nearest_bear_fvg_high=price+2,nearest_bear_fvg_created_bar=20,
        vp_poc=profiles[r[2]]['vp_poc'],vp_va_low=profiles[r[2]]['vp_va_low'],vp_va_high=profiles[r[2]]['vp_va_high']) for r in rows])
    # Actual lifecycle events, including a merge/bound update, must render one
    # connected band even when nearest selection disappears for many bars.
    zones={
        's1':dict(side='support',low=price-4,high=price-3,institutional=False),
        'r1':dict(side='resistance',low=price+3,high=price+4,institutional=False),
        'is1':dict(side='support',low=price-6,high=price-5,institutional=True),
        'ir1':dict(side='resistance',low=price+5,high=price+6,institutional=True),
    }
    events={rows[0][2]:[dict(id=k,**v,before=None) for k,v in zones.items()]}
    before=dict(zones['s1']);zones['s1']={**before,'low':price-4.5,'high':price-3.5}
    events[rows[70][2]]=[dict(id='s1',**zones['s1'],before=before)]
    conn=features_store.open_db()
    with conn:conn.executemany('UPDATE features SET sr_zone_events=? WHERE symbol=? AND interval=? AND open_time=?',[(json.dumps(events.get(r[2],[])),'BTCUSDT','15m',r[2]) for r in rows])
    conn.close()
    ob=dict(side='bull',kind='ob',strict=False,low=price-12,high=price-11,strength=1.75,created_bar=0,created_time=rows[0][2],mitigated=False)
    engine.context.persistent['obDisplayZones']={'normal:bull:0':ob}
    conn=features_store.open_db()
    with conn:conn.executemany('UPDATE features SET ob_zone_events=? WHERE symbol=? AND interval=? AND open_time=?',[(json.dumps([dict(id='normal:bull:0',**ob,before=None)] if i==0 else []),'BTCUSDT','15m',r[2]) for i,r in enumerate(rows)])
    conn.close()
    engine.context.persistent['srDisplayPrevious']=zones
    for side,ordinary,institutional in [('support','s1','is1'),('resistance','r1','ir1')]:
        engine.context.persistent[side+'ZoneIDArray']=[ordinary,institutional]
        engine.context.persistent[side+'ScoreArray']=[19.25,20]
        engine.context.persistent['inst'+side.title()+'ZoneIDArray']=[institutional]
        engine.context.persistent['inst'+side.title()+'ScoreArray']=[33.5]
    conn=features_store.open_db()
    with conn:conn.execute('UPDATE feature_engine_state SET state=? WHERE symbol=? AND interval=?',(dump(engine,(0,0)),'BTCUSDT','15m'))
    conn.close()
    step=14400000;start=(rows[-1][2]//step-3)*step
    source=[dict(symbol='BTCUSDT',interval='4h',open_time=start+i*step,close_time=start+(i+1)*step-1,
                 open=price,close=price,high=price+1,low=price-1,volume=5) for i in range(3)]
    db.write_klines(source)
    db.write_features([dict(symbol='BTCUSDT',interval='4h',open_time=b['open_time'],formula_version=3,
                     qualified_bull_fvg=i==0,bull_fvg_low=price-8,bull_fvg_high=price-7) for i,b in enumerate(source)])
    higher=Engine('BTCUSDT','4h')
    for b in source:higher.step(b)
    higher.context.persistent['srDisplayPrevious']={'higher-is1':dict(side='support',low=price-6,high=price-5,institutional=True)}
    higher.context.persistent.update(supportZoneIDArray=['higher-is1'],supportOriginTimeArray=[source[0]['open_time']],
        supportTouchArray=[12],supportStrongRejectArray=[5],supportScoreArray=[40],
        instSupportZoneIDArray=['higher-is1'],instSupportScoreArray=[56])
    conn=features_store.open_db()
    with conn:conn.execute('INSERT OR REPLACE INTO feature_engine_state VALUES (?,?,?,?)',('BTCUSDT','4h',higher.context.last_time,dump(higher,(0,0))))
    conn.close()
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
        for name in ('Market Structure','Support / Resistance','FVG','Order Blocks','Volume Profile'):
            await dialog.get_by_role('button',name=name,exact=True).click()
            await dialog.get_by_role('button',name='Select all',exact=True).click()
        await dialog.get_by_label('Point of control (POC) color',exact=True).fill('#fedcba')
        await dialog.get_by_label('Point of control (POC) width',exact=True).select_option('4')
        await dialog.get_by_label('Point of control (POC) line style',exact=True).select_option('1')
        await dialog.get_by_label('Profile bar length (% of chart)',exact=True).fill('55')
        await dialog.get_by_label('High-volume nodes bar opacity',exact=True).fill('25')
        await dialog.get_by_label('Low-volume nodes bar opacity',exact=True).fill('75')
        await dialog.get_by_role('button',name='Order Blocks',exact=True).click()
        await dialog.get_by_label('Bullish order blocks line style',exact=True).select_option('3')
        await dialog.get_by_role('button',name='Display',exact=True).click()
        await dialog.get_by_role('button',name='Deselect all scores',exact=True).click()
        assert not await dialog.get_by_label('Bullish order blocks show scores',exact=True).is_checked()
        await dialog.get_by_role('button',name='Select all scores',exact=True).click()
        assert await dialog.get_by_label('Bullish order blocks show scores',exact=True).is_checked()
        await dialog.get_by_role('button',name='Style',exact=True).click()
        await dialog.get_by_role('button',name='Support / Resistance',exact=True).click()
        await dialog.get_by_label('Support zones fill opacity',exact=True).fill('45')
        await dialog.get_by_role('button',name='Display',exact=True).click()
        await dialog.get_by_role('button',name='Deselect all scores',exact=True).click()
        assert not await dialog.get_by_label('Institutional support show scores',exact=True).is_checked()
        await dialog.get_by_role('button',name='Select all scores',exact=True).click()
        assert await dialog.get_by_label('Institutional support show scores',exact=True).is_checked()
        await dialog.get_by_label('Support zones show scores',exact=True).uncheck()
        await dialog.get_by_role('button',name='Style',exact=True).click()
        assert await dialog.get_by_label('Institutional support show scores',exact=True).count()==0
        await dialog.get_by_role('button',name='FVG',exact=True).click()
        await dialog.get_by_label('4H bullish FVG line style',exact=True).select_option('3')
        await dialog.get_by_label('Bullish FVG color',exact=True).fill('#abcdef')
        await dialog.get_by_label('Bullish FVG width',exact=True).select_option('3')
        await dialog.get_by_label('Bullish FVG line style',exact=True).select_option('2')
        await dialog.get_by_role('button',name='Apply',exact=True).click();await settle(page)
        count=await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().length)")
        await page.wait_for_function("DataCache.fvgFrames['4h']?.bars.length===3")
        await settle(page)
        count=await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().length)")
        assert count==10,count
        projected=await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().find(z=>z.identity==='4h:higher-is1'))")
        assert projected['start']==source[0]['open_time']//1000
        assert projected['score']==56 and projected['touches']==12
        assert projected['end']==rows[-1][2]//1000
        ob_band=await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().find(z=>z.key==='normal_bull_ob_zones'))")
        assert ob_band['start']==rows[0][2]//1000 and ob_band['end']==rows[-1][2]//1000
        assert ob_band['score']==1.75
        band=await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().find(z=>z.identity==='support_zones:s1'))")
        assert band['start']==rows[0][2]//1000
        assert band['end']==rows[-1][2]//1000
        assert len(band['history'])==2
        assert band['score']==19.25
        structure=await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().find(z=>z.key==='structure_range_zones'))")
        assert structure['low']==price-9 and structure['high']==price-8
        inst=await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().find(z=>z.identity==='inst_support_zones:is1'))")
        assert inst['score']==33.5
        assert await page.evaluate("import('/overlays/zones/index.js').then(x=>x.zoneScoreLabel({key:'inst_support_zones',score:33.5}))")=='I-S/R 33.50'
        assert await page.evaluate('Composer.config.featureStyles.support_zones.scores') is False
        assert await page.evaluate('DataCache.srSnapshot.through')==rows[-1][2]//1000
        higher=await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().find(z=>z.key==='bull_fvg_4h_zones'))")
        assert higher['start']==(source[0]['close_time']+1)//1000
        assert higher['end']==rows[-1][2]//1000
        assert await page.evaluate('Composer.config.featureStyles.bull_fvg_4h_zones.style')==3
        await page.evaluate("import('/overlays/volume_profile/index.js').then(x=>window.profileOverlay=x)")
        try:await page.wait_for_function("window.profileOverlay.getProfile()?.bins.length===24",timeout=10000)
        except Exception:
            print(await page.evaluate("({snapshot:DataCache.volumeProfile,last:DataCache.bars.at(-1)?.open_time,edge:DataCache.atLiveEdge,errors:DataCache.error,styles:Composer.config.featureStyles.vp_histogram})"),flush=True)
            print(requests[-10:],flush=True)
            raise
        assert await page.evaluate('Composer.config.featureStyles.vp_poc.color')=='#fedcba'
        assert await page.evaluate('Composer.config.featureStyles.vp_hvn_nodes.opacity')==25
        assert await page.evaluate('Composer.config.featureStyles.vp_lvn_nodes.opacity')==75
        for key in ('vp_poc','vp_va_high','vp_va_low'):
            plotted=await page.evaluate("key=>import('/overlays/indicators/index.js').then(x=>x.getSeries(key).data().filter(p=>p.value!=null))",key)
            expected=[{'time':r[2]//1000,'value':profiles[r[2]][key]} for r in rows]
            assert plotted==expected,(key,len(plotted))
            assert len({p['value'] for p in plotted})>1,key

        assert await page.evaluate('Composer.config.featureStyles.vp_histogram.lengthPercent')==55
        assert await page.evaluate("import('/overlays/volume_profile/index.js').then(x=>x.getProfile().levels.vp_poc)")==profiles[rows[-1][2]]['vp_poc']
        assert await page.evaluate('Composer.config.featureStyles.support_zones.opacity')==45
        assert await page.evaluate('Composer.config.featureStyles.support_zones.scores') is False
        assert await page.evaluate('Composer.config.featureStyles.bull_fvg_zones.color')=='#abcdef'
        assert await page.evaluate('Canvas.chart.panes().length')==1
        await page.screenshot(path='/tmp/tradingbot-zones.png')
        await page.reload();await sign_in(page,'user');await page.wait_for_function('window.Composer?.mounted && !DataCache.loading')
        assert await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().length)")==10
        assert await page.evaluate('Composer.config.featureStyles.vp_hvn_nodes.opacity')==25
        assert await page.evaluate('Composer.config.featureStyles.vp_lvn_nodes.opacity')==75
        await page.get_by_role('button',name='Open settings',exact=True).click()
        await dialog.get_by_role('tab',name='Features',exact=True).click()
        await dialog.get_by_role('button',name='FVG',exact=True).click()
        await dialog.get_by_role('button',name='Deselect all',exact=True).click()
        await dialog.get_by_role('button',name='Apply',exact=True).click();await settle(page)
        assert await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().length)")==7
        assert not any('/api/fvg' in url or '/api/support' in url or '/api/volume_profile' in url for url in requests)
        assert not errors,errors
        await page.get_by_role('button',name='Open settings',exact=True).click()
        await dialog.get_by_role('button',name='Display',exact=True).click()
        await dialog.get_by_role('checkbox',name='4H bullish FVG',exact=True).check()
        await dialog.get_by_role('button',name='Apply',exact=True).click();await settle(page)
        await page.evaluate("DataCache.loadInitial('BTCUSDT','4h')")
        await page.wait_for_function("!DataCache.loading && !DataCache._olderPromise")
        await settle(page)
        own=await page.evaluate("import('/overlays/zones/index.js').then(x=>x.getSegments().filter(z=>z.key==='bull_fvg_4h_zones'))")
        assert len(own)==1,own
        conn=features_store.open_db()
        with conn:conn.execute('INSERT OR REPLACE INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',('BTCUSDT','4h','test-wait',source[-1]['open_time'],source[0]['open_time'],'[]',None,json.dumps(['sr_zone_events','nearest_bull_fvg_low'])))
        conn.close()
        await page.evaluate('DataCache.refreshStored()');await settle(page)
        assert 'Zone coverage pending feature repair' in await page.locator('#status').inner_text()
        assert await page.evaluate('DataCache.bars.length')==3
        assert not errors,errors
        print('PASS: continuous OB lifecycle and Display controls, institutional scores, source-chart FVG, structure ranges, VP and combined-stream reuse',flush=True)
        await browser.close()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),exercise)
