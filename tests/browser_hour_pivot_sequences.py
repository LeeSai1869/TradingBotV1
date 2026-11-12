"""Full-cohort dashboard controls and causal DI timelines, using synthetic fixtures."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_hour_pivot_sequences import packet
from Section_8_Decision_Engine.pivot_sequences import analyze
from study_btc_hour_sequences import visual,combination_analysis,combination_visual
from test_hour_combinations import fixture
from playwright.sync_api import sync_playwright

def main():
    result=analyze(packet());result['combination_study']=combination_analysis(result)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        try:
            page=browser.new_page(viewport=dict(width=1300,height=900));errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_content(visual(result));page.get_by_role('button',name='Inspect',exact=True).first.click()
            assert page.locator('#detail svg').count()==2
            assert page.locator('#detail svg').first.evaluate('(node)=>node.namespaceURI')=='http://www.w3.org/2000/svg'
            assert page.locator('#detail svg path').count()==4
            frame=page.frame_locator('iframe[title="Combination filters"]')
            assert frame.locator('#combo-results tr').count()==3
            page.locator('#side').select_option('SELL');page.locator('#stage').select_option('origin_close')
            assert '1 pivots' in page.locator('#page').inner_text()
            page.get_by_role('button',name='Inspect',exact=True).first.click()
            assert 'LOST' not in page.locator('#counts').inner_text()
            page.set_viewport_size(dict(width=390,height=844));assert page.locator('#cases').is_visible()
            assert page.evaluate('document.body.scrollWidth<=innerWidth')
            page.goto('about:blank');page.set_content(combination_visual(combination_analysis(fixture())))
            assert page.locator('#combo-results tr').count()==3
            assert page.locator('#combo-results tr').nth(1).locator('td').nth(2).inner_text()=='3'
            assert page.locator('#combo-results tr').nth(1).locator('td').nth(3).inner_text()=='1'
            assert page.locator('#combo-results tr').nth(1).locator('td').nth(5).inner_text()=='1'
            page.locator('#combo-cohort').select_option('candidate_next_open_12h')
            assert page.locator('#combo-stage').is_disabled()
            assert '2.000%' in page.locator('#combo-results').inner_text()
            assert page.locator('#combo-chronology tr').count()==7
            page.locator('#combo-year').select_option('2026')
            assert 'unavailable' in page.locator('#combo-results').inner_text()
            assert 'QUALITY:INVALID' in page.locator('#combo-detail').text_content()
            page.locator('#combo-side').select_option('SELL')
            assert page.locator('#combo-results tr').nth(1).locator('td').nth(2).inner_text()=='0'
            assert page.evaluate('document.body.scrollWidth<=innerWidth')
            assert not errors,errors
            print('PASS cohort filters, pivot inspector, DI timelines, combination counts/exclusions, UTC years, zero samples and mobile layout')
        finally:browser.close()

if __name__=='__main__':main()
