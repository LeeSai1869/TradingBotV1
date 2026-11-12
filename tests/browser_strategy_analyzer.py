"""Offline strategy inspector: failures, revision cases, signals and mobile layout."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
from test_strategy_analyzer import source, config
from Section_8_Decision_Engine import strategy_analyzer as a
from analyze_btc_hour_strategy import visual


def main():
    report = a.analyze(source(), config())
    report['comparison'] = a.compare(report, report)
    # Enough signals to check the independent signal pager reaches its final page.
    report['signals'] = report['signals'] * 30
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        try:
            page = browser.new_page(viewport=dict(width=1300, height=900))
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.set_content(visual(report))
            assert page.locator('#trades tr').count() == 3
            page.locator('#view').select_option('failures')
            assert page.locator('#trades tr').count() == 2
            page.get_by_role('button', name='Inspect', exact=True).click()
            assert 'feature.buy@lag0' in page.locator('#detail').inner_text()
            assert 'LOSS' in page.locator('#detail').inner_text()
            page.locator('#view').select_option('comparison:failure_persisted')
            page.get_by_role('button', name='Inspect', exact=True).click()
            assert 'baseline' in page.locator('#detail').inner_text()
            assert 'revision' in page.locator('#detail').inner_text()
            assert page.locator('#signals tr').count() == 51
            page.locator('#signal-next').click();page.locator('#signal-next').click()
            assert page.locator('#signals tr').count() == 21
            assert page.locator('#signal-next').is_disabled()
            assert not page.locator('#signal-prev').is_disabled()
            assert 'Signal page 3' in page.locator('#signal-count').inner_text()
            page.set_viewport_size(dict(width=390, height=844))
            assert page.evaluate('document.body.scrollWidth <= innerWidth')
            assert not errors, errors
            print('PASS strategy failures, revision drilldown, signal evidence/pagination, missing inputs and mobile layout')
        finally:
            browser.close()


if __name__ == '__main__':
    main()
