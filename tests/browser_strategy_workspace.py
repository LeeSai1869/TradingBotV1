"""Real editor -> Python replay -> configurable report, without market writes."""
from pathlib import Path
import gzip
import json
import sys
import tempfile
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright, expect
from strategy_analyzer_workspace import Workspace, make_server
from test_strategy_analyzer import source, config


def main():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);input_file=root/'fixture.json.gz';input_file.write_bytes(gzip.compress(json.dumps(source()).encode()))
        workspace=Workspace(root/'workspace',input_file)
        paths=workspace.report_paths
        workspace.report_paths=lambda:{key:value for key,value in paths().items() if key!='published'}
        saved=workspace.save_config({'config':config()})
        server=make_server(workspace,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport=dict(width=1400,height=1000));errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                try:
                    page.goto(f'http://127.0.0.1:{server.server_port}/')
                    expect(page.locator('#run-strategy')).to_be_enabled()
                    page.locator('#strategy-preset').select_option(saved['key']);page.locator('#load-preset').click()
                    expect(page.locator('#branches-editor .branch')).to_have_count(2)
                    page.locator('#strategy-name').fill('Browser test strategy');page.locator('#strategy-name').dispatch_event('change')
                    # Create and edit a nested OR group, then save the UI configuration.
                    buy=page.locator('#branches-editor .branch').first
                    buy.get_by_role('button',name='Group OR',exact=True).click()
                    expect(buy.locator('.group-heading select')).to_have_value('any')
                    buy.locator('.predicate').nth(1).locator('select[aria-label="Condition field"]').select_option('feature.rsi')
                    buy.locator('.predicate').nth(1).locator('input[aria-label="Condition value"]').fill('99')
                    buy.locator('.predicate').nth(1).locator('input[aria-label="Condition value"]').dispatch_event('change')
                    page.locator('#save-config').click();expect(page.locator('#run-status')).to_contain_text('Strategy saved')
                    # The browser draft survives a reload; no JSON editor or terminal flags.
                    page.reload();expect(page.locator('#run-strategy')).to_be_enabled()
                    expect(page.locator('#strategy-name')).to_have_value('Browser test strategy')
                    expect(page.locator('#branches-editor .branch').first.locator('.group-heading select')).to_have_value('any')
                    page.locator('#baseline-preset').select_option(saved['key'])
                    page.get_by_text('Choose additional indicator values to record in the report',exact=True).click()
                    page.locator('#report-fields input[value="feature.rsi"]').check()
                    page.locator('#run-strategy').click()
                    expect(page.locator('#run-status')).to_contain_text('Complete',timeout=20000)
                    expect(page.locator('#summary')).to_contain_text('Completed trades')
                    expect(page.locator('#trades tr')).to_have_count(3)
                    page.locator('#view').select_option('failures')
                    expect(page.locator('#trades tr')).to_have_count(2)
                    page.get_by_role('button',name='Inspect',exact=True).click()
                    expect(page.locator('#detail')).to_contain_text('RSI')
                    expect(page.locator('#detail')).to_contain_text('Entry price')
                    page.get_by_text('Filter by a recorded indicator value',exact=True).click()
                    page.locator('#input-field').select_option('feature.rsi@lag0')
                    page.locator('#input-value').fill('60');page.locator('#input-value').dispatch_event('change')
                    expect(page.locator('#page')).to_contain_text('0 records')
                    expect(page.locator('#summary')).to_contain_text('Completed trades')
                    page.locator('#clear-filters').click()
                    page.get_by_text('Choose table columns',exact=True).click()
                    page.locator('#input-columns').select_option(['feature.rsi@lag0'])
                    expect(page.locator('#trades')).to_contain_text('RSI · BUY → SELL')
                    with page.expect_download() as downloaded:page.locator('#export-csv').click()
                    text=Path(downloaded.value.path()).read_text(encoding='utf-8-sig')
                    assert 'RSI at BUY' in text and '"50"' in text,text
                    page.locator('#pin-baseline').click();expect(page.locator('#run-status')).to_contain_text('selected as baseline')
                    with page.expect_download() as report_download:page.locator('#download-html').click()
                    assert 'Configure your report' in Path(report_download.value.path()).read_text()
                    # Upload a distinct source and check the actual replay changes.
                    different=source();different['candles'][1]['open']=100;different['candles'][1]['high']=112;different['candles'][1]['low']=98;different['source_id']='different-input'
                    other=root/'other.json.gz';other.write_bytes(gzip.compress(json.dumps(different).encode()))
                    page.locator('#input-upload').set_input_files(str(other))
                    expect(page.locator('#input-source')).to_have_value(__import__('re').compile('uploaded-'))
                    expect(page.locator('#run-strategy')).to_be_enabled()
                    page.locator('#run-strategy').click();expect(page.locator('#run-status')).to_contain_text('Complete',timeout=20000)
                    assert len(list((root/'workspace/runs').glob('*/strategy_analysis.json.gz')))==2
                    reports=[json.load(gzip.open(path,'rt')) for path in (root/'workspace/runs').glob('*/strategy_analysis.json.gz')]
                    assert len({r['contract']['memory_digest'] for r in reports})==2
                    assert len({r['summary']['mean_net_pct'] for r in reports})==2
                    page.set_viewport_size(dict(width=390,height=844))
                    assert page.evaluate('document.body.scrollWidth<=innerWidth')
                    assert not errors,errors
                    print('PASS visual AND/OR editing, saved/reloaded configuration, real Python replay/baseline, extra inputs, report filters/columns/CSV, source upload and mobile layout')
                finally:browser.close()
        finally:server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':main()
