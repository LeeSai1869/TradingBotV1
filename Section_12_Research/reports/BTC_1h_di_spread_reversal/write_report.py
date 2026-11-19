"""Write the human-readable audit from the frozen replay results."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))

import json,hashlib,gzip
from pathlib import Path
from datetime import datetime,timezone,timedelta
O=Path(__file__).parent
r=json.loads((O/'results.json').read_text());l=json.loads((O/'liquidity_verification.json').read_text())
def num(x,d=2):return '—' if x is None else f'{x:.{d}f}'
def pct(x,d=2):return num(x,d)+'%' if x is not None else '—'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(str(c) for c in row)+' |' for row in rows])
def pkt(iso):return datetime.fromisoformat(iso).astimezone(timezone(timedelta(hours=5))).isoformat()
lines=['# BTC 1h: DI-spread first-drop spot hypothesis','','**Superseded exit-policy comparison:** see the [corrected 0.5% stop / regime-dependent trailing and 5m-confluence replay](../BTC_1h_di_spread_trailing_v2/README.md). The fixed-target / 24-hour experiment below is historical, not the current user specification.','',
'13 November 2026. Research only. The latest example reached its target, but the complete sample does not establish a standalone trading edge. No live BUY/SELL rules, indicator formulas, feature retention or ADCN fields were changed.','',
'## Frozen test definition','',
'- BTCUSDT spot, 80,884 stored hourly candles from '+r['coverage']['first_utc']+' through '+r['coverage']['last_closed_utc']+'. The exported current feature generation is 1. Stored RSI length is **7**, ADX/DI length **10**; this is not a standard RSI(14) substitution.',
'- Bearish spread = DI− minus DI+. It equals the chart’s absolute DI spread while DI− dominates. A local peak is known after the first subsequent closed decline: spread[t−1] ≥ spread[t−2] and spread[t] < spread[t−1]. Flat-topped peaks count. This never chooses the highest future spread or a retrospective pivot low.',
'- Primary test requires spread above 40 both at the peak and at confirmation; DI− above 40 / 45 / 50 at confirmation. Each threshold is tested with and without RSI below 20 at confirmation. Peak-time thresholds and peak-only spread are separate sensitivity Section_13_Development/tests in results.json.',
'- Enter at the **next hourly open**, after the signal candle is closed. A forming-candle DI drop cannot be replayed accurately from final hourly measurements alone; an intrabar implementation needs a separate lower-timeframe test.',
'- Sell at the first hourly high touching the precomputed +1% **net** target. Costs retain the earlier research scenario: 4 bps fee and 2 bps slippage **per side**. That requires a '+pct(r['costs']['required_price_rise_pct'],4)+' reference-price rise. A gross 1% price move instead yields about '+pct(r['costs']['net_after_gross_1pct'],4)+' net in this scenario. A 10 bps fee sensitivity is also saved.',
'- Commission rates depend on the actual account/symbol; the assumed costs are not an account-rate claim. Binance documents the account commission endpoint in its [commission FAQ](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/commission_faq.md).',
'- Your proposed policy has no specified stop or timeout. Accordingly, unlimited-hold replays are included. Fixed 6 / 12 / 24 / 48 / 72 / 168-hour windows and stop sensitivities are comparison experiments, not newly adopted production exits.',
'- Missing or discontinuous candles censor the forward outcome. Incomplete final windows are excluded from fixed-horizon hit rates even when an early target hit is already known. Event outcomes may overlap; separate single-position replays skip overlapping entries.','',
'## How often did the 1% net target arrive within 24 hours?','',
'The average-return column takes +1% at a target hit and marks an unresolved position to market at the 24-hour close. It answers a defined 24-hour experiment, not the profitability of holding indefinitely.','']
rows=[]
for t in (40,45,50):
 for rs in (False,True):
  v=r['variants'][f'di_minus_gt_{t}'+('_rsi_lt_20' if rs else '')]['horizons']['24'];rows.append([f'> {t}','< 20' if rs else 'No RSI gate',v['evaluable'],v['target_hits'],pct(v['target_hit_pct']),pct(v['mean_net_pct'])])
lines += [table(['DI−','RSI','Eligible completed windows','Target hits','Hit rate','Mean net, 24h experiment'],rows),'',
'RSI below 20 changes these hit rates only slightly and reduces the sample. Raising DI− to 50 does not improve target attainment. The comparison does not justify selecting 45 as a final production threshold.','',
'For DI− >45 and RSI <20:','']
v=r['variants']['di_minus_gt_45_rsi_lt_20']
lines += [table(['Window','Eligible','Target hit rate','Mean net at target / window close'],[[h+'h',s['evaluable'],pct(s['target_hit_pct']),pct(s['mean_net_pct'])] for h,s in v['horizons'].items()]),'',
'The non-overlapping 24-hour replay has '+str(v['single_position']['no_stop']['evaluable'])+' fully observable trades, '+pct(v['single_position']['no_stop']['target_hit_pct'])+' target attainment and '+pct(v['single_position']['no_stop']['mean_net_pct'])+' mean net return. The same negative conclusion survives removing overlapping entries.','',
'## Holding until 1% is not a free exit','',
'Unlimited-hold Section_13_Development/tests must retain unresolved positions and missing-data censoring; a 100% win rate among only completed target exits is not a valid success rate. For the DI− >45 / RSI <20 single-position replay:','']
u=v['single_position']['no_time_limit_no_stop']
for x in u['longest_holds']:
 lines.append(f"- Entry {x['entry_utc']}; {x['status']}; observed for {x['hours']} hours ({x['hours']/24:.1f} days); adverse excursion bound {pct(x['adverse_bound_pct'])}. Censored entries have no claimed completed-trade return.")
for x in u['censored_positions']:
 if x['status']=='RIGHT_CENSORED':lines.append(f"- The position entered {x['entry_utc']} is still unresolved at the dataset boundary: last-close mark to market **{pct(x['last_known_mtm_pct'])}**, after {x['bars']/24:.1f} days. This is an observed open position, not a hypothetical stop loss.")
lines += ['',
'The eventual-hit statistics and compounded completed-trade returns exclude unpriced censored outcomes. They must not be presented as total account returns; results.json explicitly marks unlimited-hold account return as invalid when censored positions exist.','',
'## Bearish trend, regime and additional features','',
'The context uses the existing Section 5 engine functions, replayed sequentially offline: original Section 4 Structure event lineage → Structure → Trend, plus Regime. Source/config hashes are recorded. This supplies the current definitions over the complete research sample without waiting for production history backfill. These are reconstructed close-time classifications, not proof they were published live at those historical times. PARTIAL quality remains labelled; missing context is never converted to bullish/neutral.','',
'For DI− >45 / RSI <20, separating an established bearish *regime* from other known regimes:','',
 table(['Regime','Eligible 24h windows','Hit rate','Mean net, 24h'],[[k,s['evaluable'],pct(s['target_hit_pct']),pct(s['mean_net_pct'])] for k,s in v['by_trending_bearish_regime'].items()]),'',
'The bearish regime has a worse average outcome in this comparison, even though its target-hit frequency is higher. Trend direction alone is not a sufficient skip rule: sharp selloffs frequently produce confirmed bearish direction as well as oversold measurements. The report keeps confirmed Trend separate from retained direction during pending/conflicted conditions.','',
'Nine additional gates were checked within the bearish Trend-direction subset. All were predetermined simple conditions; no grid search was run. 2017–2023 is discovery, 2024 validation, and 2025–2026 a chronological holdout. Forward windows crossing a split boundary are excluded. Since the hypothesis came from already viewed charts, this holdout is not prospective validation.','']
filters=r['bearish_filter_tests']['di_minus_gt_45_rsi_lt_20'];rows=[]
for name,s in filters.items():
 a=s['discovery_2017_2023'];b=s['holdout_2025_2026'];rows.append([name,a['evaluable'],pct(a['mean_net_pct']),b['evaluable'],pct(b['mean_net_pct'])])
lines += [table(['Additional bearish-condition gate','Discovery N','Discovery mean net','2025–26 N','2025–26 mean net'],rows),'',
'**No additional gate demonstrates a validated fix.** NATR ≥1% improves full-sample target frequency, but discovery expectancy remains negative and the holdout is tiny. Excluding a trending bearish regime has some positive recent subsets but too few observations, with negative discovery expectancy. RSI rising, DI+ rising, upper-range closes, volume, EMA distance and weakening Trend do not establish a consistent advantage here. These features can remain research/risk inputs; this result authorizes no memory pruning.','',
'## Latest example','']
e=v['events'][-1]
lines += [f"The {e['signal_utc']} signal candle was known at **{pkt(e['entry_utc'])} PKT**. DI− {e['di_minus']:.2f}, spread {e['spread']:.2f} after a {e['peak_spread']:.2f} peak, RSI {e['rsi']:.2f}. The next open was {e['entry_open']:,.2f}; the net-target reference price was {e['target_reference']:,.2f}.",'',
'Price touched that target in the third hourly candle after entry (12:00–13:00 PKT). This verifies the recent example under the hourly-touch assumptions. DI− had already dropped below 50 at confirmation, so the strict current-value >50 version did not take it. Its full 24-hour observation window had not ended when the source was frozen; it is excluded from the fixed-horizon aggregate denominator.','',
'## Liquidity: what was wrong and what changed','',
'- The recorder is delivering real Binance **USDT perpetual** depth. It is not spot depth. A finite 1,000-level snapshot was covering only a few tenths of a percent below price and less above it; small bands do not mean a full 1% book was observed.',
'- Sequence recoveries and delayed exchange messages caused real gaps. One earlier 120-sample inspection found a maximum sample interruption of 168 seconds. Stale depth is intentionally hidden; keeping it drawn as current would misrepresent the book.',
'- The computer clock was within about 0.1 seconds of Binance’s public time endpoints. The recurring “delayed exchange book or local clock skew” message was therefore not evidence that the clock itself was wrong.',
'- A busy raw archive batch held newly queued current samples behind up to 1,000 raw writes. The writer now returns to current-sample commits after a bounded 50ms raw-work slice, preserving every queued raw record. Only the existing liquidity service was restarted, preserving configuration and data.',
'- After restart, '+str(l['after_write_delay_ms']['n'])+' BTC samples over '+num(l['after_window_seconds'],1)+' seconds had median sample-to-memory delay **'+num(l['after_write_delay_ms']['median'],0)+'ms**, versus **'+num(l['before_write_delay_ms']['median'],1)+'ms** before. The after-window maximum remained '+num(l['after_write_delay_ms']['max'],0)+'ms. This short observation is not proof that transport interruptions are eliminated.',
'- Current profiles now draw above shaded overlays, with a one-pixel minimum for subpixel price bins. Original prices/notional remain exact; the forming-candle strip stays clear. The heatmap remains below candles and keeps exact observed times. Freshness limits and historical-view restrictions remain enforced.',
'- Reload the chart to load this display correction. Native app visual inspection was unavailable; the rendering geometry, stale hiding, market restrictions and candle protection are covered by automated checks.',
'- This feed cannot be added as a universal historical entry gate: matching historical spot/perpetual observations were not recorded for most of this candle archive. No synthetic historical liquidity was added.','',
'## Reproduce and inspect','',
'- `source.json.gz`: frozen measurements, engine definitions/configuration and offline context; SHA-256 of the decompressed source '+hashlib.sha256(gzip.decompress((O/'source.json.gz').read_bytes())).hexdigest()+'.',
'- `results.json`: all six variants, every signal with context/prices, horizons, exact timing sensitivities, non-overlapping replays, costs, stop ambiguity, censored positions and bearish-filter splits.',
'- `liquidity_verification.json`: before/after timing, coverage, clock check, live status and observation limits.',
'- Replay the frozen source: `PYTHONPATH=. .venv-build/bin/python3 Section_12_Research/reports/BTC_1h_di_spread_reversal/study.py`.',
'- A new read-only export can be made with `export_source.py`. It releases source database read snapshots before running the longer offline classifiers. A fresh export changes the frozen observation window.',
'- Verification: 29 Python Section_13_Development/tests passed for the liquidity recorder/analytics and replay semantics; 10 JavaScript liquidity-display Section_13_Development/tests passed. Target touches remain an OHLC fill approximation. Stop and target in the same hourly candle use stop-first ordering, except a gap-up opening already through the target.','',
'Keep this as an exhaustion-watch hypothesis. A usable buy/sell rule still needs a supported entry filter plus a defined loss/time/capital policy; a frequent rebound is not enough to establish positive expectancy.','']
(O/'README.md').write_text('\n'.join(lines))
print(O/'README.md')
