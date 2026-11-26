import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=await browser.new_page(viewport={'width':1450,'height':1100});errors=[];external=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('request',lambda r:external.append(r.url) if r.url.startswith(('https:','http:')) else None)
  await page.set_content((Path(__file__).resolve().parents[2]/'Section_12_Research/experiments/pivot_confirmation/comparison.html').read_text())
  assert await page.locator('#summary tbody tr').count()==3
  assert '528' in await page.locator('#summary').inner_text()
  await page.locator('#placement').select_option('confirmation_time')
  await page.locator('#variant').select_option('confirmed_pair_only')
  await page.locator('#size').select_option('6000')
  await page.locator('#latest').click()
  await page.locator('#size').select_option('650')
  await page.locator('#latest').click()
  await page.locator('#new').hover()
  assert 'PKT' in await page.locator('#tip').inner_text()
  await page.set_viewport_size({'width':390,'height':844})
  await page.screenshot(path='/tmp/pivot-trial-mobile.png',full_page=True)
  assert not errors,errors
  assert not external,external
  print('PASS: standalone view, rule selection, recognition-time placement, 6000-candle range, hover details, mobile rendering, no external requests')
  await browser.close()
asyncio.run(main())
