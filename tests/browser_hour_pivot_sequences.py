"""Full-cohort dashboard controls and causal DI timelines, using synthetic fixtures."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_hour_pivot_sequences import packet
from Section_8_Decision_Engine.pivot_sequences import analyze
from study_btc_hour_sequences import visual
from playwright.sync_api import sync_playwright

def main():
    result=analyze(packet())
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        try:
            page=browser.new_page(viewport=dict(width=1300,height=900));errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_content(visual(result));page.get_by_role('button',name='Inspect',exact=True).first.click()
            assert page.locator('#detail svg').count()==2
            assert page.locator('#detail svg').first.evaluate('(node)=>node.namespaceURI')=='http://www.w3.org/2000/svg'
            assert page.locator('#detail svg path').count()==4
            page.locator('#side').select_option('SELL');page.locator('#stage').select_option('origin_close')
            assert '1 pivots' in page.locator('#page').inner_text()
            page.get_by_role('button',name='Inspect',exact=True).first.click()
            assert 'LOST' not in page.locator('#counts').inner_text()
            page.set_viewport_size(dict(width=390,height=844));assert page.locator('#cases').is_visible()
            assert page.evaluate('document.body.scrollWidth<=innerWidth')
            assert not errors,errors
            print('PASS cohort filters, every-pivot inspector, SVG DI timelines and mobile layout')
        finally:browser.close()

if __name__=='__main__':main()
