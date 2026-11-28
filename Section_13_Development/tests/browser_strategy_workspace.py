"""Real editor -> Python replay -> configurable report, without market writes."""

from Section_1_Global_Core.paths import REPO_ROOT
from pathlib import Path
import gzip
import json
import sys
import tempfile
import threading
sys.path.insert(0,str(REPO_ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright, expect
from Section_12_Research.cli.strategy_analyzer_workspace import Workspace, make_server
from test_strategy_analyzer import source, config


def choose_field(predicate,field,index=0):
    menu=predicate.locator('.field-dropdown').nth(index)
    menu.locator('summary').click()
    menu.get_by_role('searchbox',name='Search fields').fill(field)
    menu.locator('[role="option"][data-field="'+field+'"]').click()


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
                    # Search is inside the opened field dropdown, with Escape support.
                    picker=page.locator('.predicate').first.locator('.field-dropdown')
                    picker.locator('summary').click();picker.get_by_role('searchbox',name='Search fields').fill('RSI')
                    expect(picker.locator('[role=option][data-field="feature.rsi"]')).to_be_visible()
                    page.screenshot(path='/tmp/analyzer-field-search.png',full_page=True)
                    picker.get_by_role('searchbox',name='Search fields').press('Escape')
                    expect(picker.locator('summary')).to_have_attribute('aria-expanded','false')
                    # A fresh workspace never chooses a preset or trading condition.
                    expect(page.locator('#strategy-preset')).to_have_value('')
                    expect(page.locator('#branches-editor .branch')).to_have_count(2)
                    for predicate in page.locator('.predicate').all():
                        expect(predicate.locator('[aria-label="Condition field"]')).to_have_value('')
                        expect(predicate.locator('[aria-label="Condition comparison"]')).to_have_value('')
                        expect(predicate.locator('[aria-label="Condition value"]')).to_have_value('')
                    page.locator('section[aria-labelledby="strategy-title"]').screenshot(path='/tmp/blank-strategy-builder.png')
                    page.locator('#run-strategy').click()
                    expect(page.locator('#workspace-error')).to_contain_text('choose an indicator')
                    for index,field in enumerate(('feature.buy','feature.sell')):
                        predicate=page.locator('#branches-editor .branch').nth(index).locator('.predicate')
                        choose_field(predicate,field)
                        predicate.locator('[aria-label="Condition comparison"]').select_option('eq')
                        if index==0:
                            page.locator('#run-strategy').click()
                            expect(page.locator('#workspace-error')).to_contain_text('enter a comparison value')
                        predicate.locator('[aria-label="Condition value"]').fill('1')
                        predicate.locator('[aria-label="Condition value"]').dispatch_event('change')
                    page.locator('#strategy-name').fill('Custom stored-data strategy');page.locator('#strategy-name').dispatch_event('change')
                    for control in ('fee','slippage'):
                        page.locator('#'+control).fill('0');page.locator('#'+control).dispatch_event('change')
                    page.locator('#new-strategy').click()
                    expect(page.locator('#branches-editor .branch').first.locator('[aria-label="Condition field"]')).to_have_value('')
                    page.reload();expect(page.locator('#run-strategy')).to_be_enabled()
                    expect(page.locator('#undo-new-strategy')).to_be_visible()
                    page.locator('#undo-new-strategy').click()
                    expect(page.locator('#strategy-name')).to_have_value('Custom stored-data strategy')
                    expect(page.locator('#fee')).to_have_value('0')
                    page.locator('#run-strategy').click()
                    expect(page.locator('#run-status')).to_contain_text('Complete',timeout=20000)
                    expect(page.locator('#trades tr')).to_have_count(3)
                    page.locator('#add-trailing-sell').click()
                    trail=page.locator('#branches-editor .branch').last
                    expect(trail.get_by_label('Trailing activation',exact=True)).to_have_value('position')
                    expect(trail.locator('.predicate')).to_have_count(0)
                    expect(trail.locator('.rule-preview')).to_contain_text('No indicator condition is required')
                    page.locator('#save-config').click();expect(page.locator('#run-status')).to_contain_text('Strategy saved')
                    page.reload();expect(page.locator('#run-strategy')).to_be_enabled()
                    trail=page.locator('#branches-editor .branch').last
                    expect(trail.get_by_label('Trailing activation',exact=True)).to_have_value('position')
                    trail.get_by_label('Trailing activation',exact=True).select_option('conditions')
                    expect(trail.locator('.predicate')).to_have_count(1)
                    page.locator('#save-config').click()
                    expect(page.locator('#workspace-error')).to_contain_text('SELL: choose an indicator')
                    trail.get_by_label('Trailing activation',exact=True).select_option('position')
                    page.locator('#preset-options summary').click()
                    page.locator('#strategy-preset').select_option(saved['key']);page.locator('#strategy-preset').dispatch_event('change');page.locator('#load-preset').click()
                    expect(page.locator('#branches-editor .branch')).to_have_count(2)
                    page.locator('#strategy-name').fill('Browser test strategy');page.locator('#strategy-name').dispatch_event('change')
                    # Create and edit a nested OR group, then save the UI configuration.
                    buy=page.locator('#branches-editor .branch').first
                    buy.get_by_role('button',name='Group OR',exact=True).click()
                    expect(buy.locator('.group-heading select')).to_have_value('any')
                    choose_field(buy.locator('.predicate').nth(1),'feature.rsi')
                    buy.locator('.predicate').nth(1).locator('[aria-label="Condition comparison"]').select_option('eq')
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
                    assert len(list((root/'workspace/runs').glob('*/strategy_analysis.json.gz')))==3
                    reports=[json.load(gzip.open(path,'rt')) for path in (root/'workspace/runs').glob('*/strategy_analysis.json.gz')]
                    assert len({r['contract']['memory_digest'] for r in reports})==2
                    assert len({r['summary']['mean_net_pct'] for r in reports})==2
                    page.set_viewport_size(dict(width=390,height=844))
                    page.wait_for_function('document.body.scrollWidth<=innerWidth')
                    page.screenshot(path='/tmp/blank-builder-mobile.png',full_page=True)
                    assert page.evaluate('document.body.scrollWidth<=innerWidth'),page.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1&&getComputedStyle(e).position!=='absolute').slice(0,12).map(e=>[e.tagName,e.id,e.className,e.getBoundingClientRect().width])")
                    assert not errors,errors
                    print('PASS blank custom strategy, incomplete-rule validation, undo, real custom replay, optional presets, visual AND/OR editing, saved/reloaded configuration, real Python replay/baseline, extra inputs, report filters/columns/CSV, source upload and mobile layout')
                finally:browser.close()
        finally:server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':main()
