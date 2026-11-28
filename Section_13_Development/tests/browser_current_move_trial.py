"""Standalone offline research viewer; no app server or market worker."""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[2]

def main():
    path=ROOT/'Section_12_Research/experiments/current_move_pivots/results/ENAUSDT-15m-comparison.html'
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        try:
            page=browser.new_page(viewport=dict(width=1450,height=1150));errors=[];external=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:external.append(r.url) if r.url.startswith(('http:','https:')) else None)
            page.set_content(path.read_text(),wait_until='load')
            expect(page.locator('#summary tbody tr')).to_have_count(3)
            expect(page.locator('#new-title')).to_have_text('Current move + two closes')
            page.locator('#placement').select_option('confirmation_time');page.locator('#placement').dispatch_event('input')
            page.locator('#variant').select_option('current_move_only');page.locator('#variant').dispatch_event('input')
            expect(page.locator('#new-title')).to_have_text('Current move only')
            page.locator('#variant').select_option('current_move_two_closes');page.locator('#variant').dispatch_event('input')
            page.locator('#latest').click();page.screenshot(path='/tmp/current-move-ENA-trial.png',full_page=True)
            page.locator('#new').hover(position=dict(x=700,y=120))
            expect(page.locator('#tip')).to_contain_text('Threshold')
            page.goto('about:blank')
            page.set_content(path.with_name('constructed-price-example.html').read_text(),wait_until='load')
            expect(page.locator('h1')).to_contain_text('not historical candles')
            expect(page.locator('#summary tbody tr')).to_have_count(3)
            assert not errors,errors
            assert not external,external
            print('PASS standalone charts, rule comparison, confirmation-time view, hover thresholds, constructed example, zero external requests')
        finally:browser.close()

if __name__=='__main__':main()
