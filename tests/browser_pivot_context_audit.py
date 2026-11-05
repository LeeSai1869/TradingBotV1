"""Render a generated offline audit on desktop/mobile without network access."""
import gzip
import json
from pathlib import Path
import sys
import tempfile
from playwright.sync_api import sync_playwright
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit_pivot_context import dashboard

def main():
    path=Path(sys.argv[1]);payload=path.read_bytes();packet=json.loads(gzip.decompress(payload) if path.suffix=='.gz' else payload)
    with tempfile.TemporaryDirectory() as folder,sync_playwright() as p:
        html=Path(folder)/'audit.html';html.write_text(dashboard(packet));errors=[];requests=[]
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        try:
            page=browser.new_page(viewport=dict(width=1300,height=900));page.on('pageerror',lambda error:errors.append(str(error)));page.on('request',lambda request:requests.append(request.url))
            page.set_content(html.read_text());assert packet['symbol'] in page.locator('h1').inner_text()
            assert packet['cohort'] in page.locator('body').inner_text();assert page.locator('meter').count()>0
            assert page.locator('details').count()>=len(packet['cases'][:40])
            page.screenshot(path='/tmp/pivot_context_audit.png')
            page.set_viewport_size(dict(width=390,height=844));page.set_content(html.read_text())
            assert page.locator('h1').is_visible();assert not errors,errors
            assert not [r for r in requests if r.startswith(('http:','https:'))],requests
        finally:browser.close()
    print('Offline audit dashboard desktop/mobile passed')

if __name__=='__main__':main()
