"""Offline every-pivot trajectory viewer, including missing values and mobile."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compare_pivot_features import visual
from playwright.sync_api import sync_playwright

def main():
    groups=[dict(side=side,outcome=outcome,year='ALL',pivots=10,count=[10,10,9],mean=mean) for side in ('BUY_SIDE','SELL_SIDE') for outcome,mean in [('HIT',[30,40,25]),('NO_HIT',[20,None,30])]]
    packet=dict(symbol='BTCUSDT',timeframe='1h',pivots=40,offsets=[-1,0,1],features={'di_minus':groups,'di_plus':groups})
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        try:
            page=browser.new_page(viewport=dict(width=1200,height=900));errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_content(visual(packet));assert page.locator('svg path').count()==2
            page.locator('#side').select_option('SELL_SIDE');page.locator('#feature').select_option('di_plus')
            assert 'HIT: 10 pivots' in page.locator('#note').inner_text()
            page.set_viewport_size(dict(width=390,height=844));assert page.locator('#plot').is_visible()
            assert page.evaluate('document.body.scrollWidth <= innerWidth')
            assert not errors,errors
            print('PASS all-pivot feature curves, controls, missing points and mobile layout')
        finally:browser.close()

if __name__=='__main__':main()
