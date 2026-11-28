"""Mark conditions, retain a setup, activate later, and inspect recorded evidence."""
from pathlib import Path
import gzip,json,tempfile,threading
from playwright.sync_api import sync_playwright,expect
from Section_12_Research.cli.strategy_analyzer_workspace import Workspace,make_server
from test_strategy_analyzer import source,config

def main():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);data=source()
        for i,row in enumerate(data['candles']):row['features'].update(buy=int(i==0),rsi=(10,20,45)[i] if i<3 else 50)
        path=root/'input.json.gz';path.write_bytes(gzip.compress(json.dumps(data).encode()))
        workspace=Workspace(root/'workspace',path)
        paths=workspace.report_paths;workspace.report_paths=lambda:{k:v for k,v in paths().items() if k!='published'}
        c=config();c['branches'][0]['when']={'all':[dict(field='feature.buy',op='eq',value=1),dict(field='feature.rsi',op='gte',value=40)]}
        saved=workspace.save_config({'config':c});server=make_server(workspace,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
                try:
                    page=browser.new_page(viewport=dict(width=1450,height=1100));errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(f'http://127.0.0.1:{server.server_port}/');expect(page.locator('#run-strategy')).to_be_enabled()
                    expect(page.locator('#replay-period')).to_have_value('full')
                    expect(page.locator('#replay-since')).to_have_value('')
                    page.locator('#replay-period').select_option('6')
                    expected_end=__import__('datetime').datetime.fromtimestamp((data['candles'][-1]['close_time']//60000+1)*60,__import__('datetime').timezone.utc)
                    expect(page.locator('#replay-until')).to_have_value(expected_end.strftime('%Y-%m-%dT%H:%M'))
                    assert page.locator('#replay-since').input_value()<page.locator('#replay-until').input_value()
                    page.reload();expect(page.locator('#run-strategy')).to_be_enabled()
                    expect(page.locator('#replay-period')).to_have_value('6')
                    page.locator('#replay-period').select_option('custom')
                    expect(page.locator('#replay-since')).to_be_editable()
                    page.locator('#replay-period').select_option('48')
                    assert int(page.locator('#replay-since').input_value()[:4])==expected_end.year-4
                    page.locator('#replay-period').select_option('full')
                    expect(page.locator('#replay-until')).to_have_value('')
                    page.locator('#preset-options summary').click();page.locator('#strategy-preset').select_option(saved['key']);page.locator('#load-preset').click()
                    buy=page.locator('#branches-editor .branch').first
                    expect(buy.get_by_label('BUY execution timing',exact=True)).to_have_value('next_open')
                    expect(page.get_by_label('SELL execution timing',exact=True)).to_have_value('next_open')
                    page.locator('#hard-stop-mode').select_option('off')
                    expect(page.locator('#risk-scope')).to_contain_text('hard stop: OFF')
                    buy.get_by_label('Condition role',exact=True).first.select_option('trigger')
                    expect(buy.locator('.rule-preview')).to_contain_text('remember setup')
                    expect(buy.get_by_label('Activation timing',exact=True)).to_have_value('same_or_later')
                    buy.get_by_label('Condition role',exact=True).nth(1).select_option('trigger')
                    page.locator('#save-config').click();expect(page.locator('#workspace-error')).to_contain_text('add at least one Activate')
                    buy.get_by_label('Condition role',exact=True).nth(1).select_option('activate')
                    page.locator('#save-config').click();expect(page.locator('#run-status')).to_contain_text('Strategy saved')
                    page.reload();expect(page.locator('#run-strategy')).to_be_enabled()
                    expect(page.locator('#hard-stop-mode')).to_have_value('off')
                    buy=page.locator('#branches-editor .branch').first
                    expect(buy.get_by_label('Condition role',exact=True).first).to_have_value('trigger')
                    expect(buy.get_by_label('Condition role',exact=True).nth(1)).to_have_value('activate')
                    page.locator('#run-strategy').click();expect(page.locator('#run-status')).to_contain_text('Complete',timeout=20000)
                    expect(page.locator('#setup-section')).to_be_visible()
                    expect(page.locator('#setups')).to_contain_text('Trigger remembered');expect(page.locator('#setups')).to_contain_text('Activated')
                    expect(page.locator('#setups tr')).to_have_count(3)
                    page.get_by_role('button',name='Inspect',exact=True).first.click()
                    expect(page.locator('#detail')).to_contain_text('BUY Trigger remembered')
                    reports=[json.load(gzip.open(path,'rt')) for path in (root/'workspace/runs').glob('*/strategy_analysis.json.gz')]
                    self_report=reports[0];signal=self_report['signals'][0]
                    assert self_report['config']['execution']['hard_stop_pct'] is None
                    assert self_report['contract']['risk_budget_pct'] is None
                    assert self_report['config']['branches'][0]['execution_timing']=='next_open'
                    assert self_report['config']['branches'][1]['execution_timing']=='next_open'
                    assert self_report['trades'][0]['entry_time']==data['candles'][3]['open_time']
                    assert signal['candle_open_time']==data['candles'][2]['open_time'],signal
                    assert signal['trigger_known_time']==data['candles'][0]['close_time']+1,signal
                    assert signal['trigger_inputs']['feature.buy@lag0']['value']==1
                    assert signal['inputs']['feature.buy@lag0']['value']==0
                    page.screenshot(path='/tmp/strategy-trigger-activate-report.png',full_page=True)
                    page.set_viewport_size(dict(width=390,height=844));page.wait_for_function('document.body.scrollWidth<=innerWidth')
                    # Legacy all-unknown reports must not imply a zero-return backtest.
                    from copy import deepcopy
                    blocked=deepcopy(self_report);blocked.pop('test_status',None)
                    blocked['signals']=[];blocked['trades']=[]
                    for stats in blocked['branch_diagnostics'].values():
                        if stats['side']=='BUY':stats['unknown']=stats['evaluated']
                    page.evaluate('(report)=>StrategyReport.mount(document.querySelector("#report-area"),report)',blocked)
                    expect(page.locator('#report-verdict')).to_contain_text('Test blocked by unavailable inputs')
                    cards=page.locator('#summary .card').filter(has_text='Closed-trade return')
                    expect(cards.locator('strong')).to_have_text('unavailable')
                    expect(page.locator('#equity-chart svg')).to_have_count(0)
                    assert not errors,errors
                    print('PASS per-condition roles, validation, persisted draft, remembered trigger, later activation, original evidence and mobile report')
                finally:browser.close()
        finally:server.shutdown();server.server_close();thread.join(timeout=3)

if __name__=='__main__':main()
