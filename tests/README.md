Run from the repository root:

```bash
node --test tests/ui_lifecycle.test.mjs
/workspace/.venvs/tradingbot/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

These tests use disposable SQLite databases and never fetch market data. They cover stale initial loads and live responses, serial polling, live rollover, prefetch ownership, partial-window compensation, calendar-month boundaries, canonical identity alignment, missing derived rows, HTTP delivery and the actual feature builder.

For the optional real-browser check, install Playwright in a development environment and provide Chromium at `/usr/bin/chromium`. Obtain the pinned chart library through npm, which verifies package integrity:

```bash
mkdir -p /workspace/.cache
npm pack lightweight-charts@5.2.1 --cache /workspace/.cache/npm --pack-destination /workspace/.cache
tar -xzf /workspace/.cache/lightweight-charts-5.2.1.tgz -C /workspace/.cache package/dist/lightweight-charts.standalone.production.js
PYTHONPATH=. python3 tests/browser_smoke.py /workspace/.cache/package/dist/lightweight-charts.standalone.production.js
```

The browser check runs the real UI and chart library against disposable generated data. It intercepts the CDN script request with the npm artifact and substitutes live candle/metadata responses. It does not validate Binance access or trading decisions.

The uploaded live configuration registers only `Section_4_Features.processor`. No application caller persists decisions with `db.write_adcn()`. Reading decision fixtures works, but live signal generation and persistence are not established by these tests. The local databases are excluded from Git and were not uploaded.

The existing architecture check (`python -m Section_1_Global_Core.tools.check_imports`) fails on this checkout. It rejects the storage gateway imports already used by the UI and feature processor; the integration fixtures also import those stores to isolate their databases. The gateway and the checker enforce conflicting contracts. This change leaves the locked Global Core and that policy unchanged; passing behavioral tests do not establish architecture-check compliance.
