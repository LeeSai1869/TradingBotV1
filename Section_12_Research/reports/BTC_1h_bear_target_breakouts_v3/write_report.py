"""Summarize fixed bearish target, audit and predefined execution filters."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))

from datetime import datetime,timezone,timedelta
from dataclasses import asdict
from pathlib import Path
import gzip,json,hashlib
P=Path(__file__).parent
r=json.loads((P/'results.json').read_text())
def num(x,d=2):return '—' if x is None else f'{x:.{d}f}'
def pct(x,d=2):return num(x,d)+'%' if x is not None else '—'
def pkt(t):return datetime.fromtimestamp(t/1000,timezone(timedelta(hours=5))).isoformat()
def table(head,rows):return '\n'.join(['| '+' | '.join(head)+' |','| '+' | '.join('---' for _ in head)+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])
def v(t,gate='immediate',method='forming_hour_drop_with_5m_peak',rsi='none'):return r['variants'][f'{method}_di{t}_rsi_{rsi}_{gate}']
def low(item,policy='new_exit'):return item['replays'][policy]['low_first']
def mean_range(item,policy='new_exit'):
 a=low(item,policy)['mean_net_pct'];b=item['replays'][policy]['high_first']['mean_net_pct'];return f'{min(a,b):.3f}% to {max(a,b):.3f}%' if a is not None and b is not None else '—'
# Collapse repeated observed flags for review; this changes no strategy entries.
events=json.loads(gzip.decompress((P/'market_events.json.gz').read_bytes()));last={};starts=[];counts={}
for e in events:
 tags=[]
 for key in ('breakout_up','breakdown','crash','breakout_retest'):
  if e[key]:
   if key not in last or e['time']-last[key]>900000:tags.append(key);counts[key]=counts.get(key,0)+1
   last[key]=e['time']
 if tags:starts.append(dict(time=e['time'],known_time=e['known_time'],time_pkt=pkt(e['known_time']),starts=tags,rvol=e['rvol'],tr_atr=e['tr_atr'],return_5m_pct=e['return_5m_pct'],prior_high=e['prior_high'],prior_low=e['prior_low']))
(P/'event_review.json').write_text(json.dumps(dict(definition='A fresh observed flag after more than 15 minutes without the same flag. Starts are known at the current 5m close; no future peak labels. No trading rules were changed by this review grouping.',episode_start_counts=counts,latest_starts=starts[-50:]),indent=2)+'\n')
a=r['audit']
lines=['# BTC: bearish +1% target, unchanged bullish trail, breakout/crash execution audit','',
'13 November 2026 (Asia/Karachi). Offline research on the same frozen BTCUSDT spot archive: 80,884 hourly candles and 970,429 recorded five-minute candles, ending 13 November 2026 at 20:59:59.999 PKT. There were no production strategy, feature, chart or service changes, no memory pruning and no orders.','',
'The stored chart settings remain RSI(7) and DI/ADX length 10. Hourly closed values and terminal forming-hour previews were previously reproduced exactly, and sampled stored 5m DI/RSI values also matched exactly.','',
'## User policy now tested','',
'- **Bearish Regime:** exit directly at the +1% profit target. This replaces bearish trailing activation.',
'- **Bullish Regime:** keep the existing logic: profit ≥1% AND known DI+ >50 activates the 0.5% highest-since-BUY trailing stop. Once armed, keep it armed.',
'- Protection remains active from entry on every trade. The main scenario targets a **0.5% net-loss budget**, with a literal **0.5% price-stop** comparison. No 24-hour exit, averaging down, pyramiding or price-low hindsight fill is used.',
'- Main target is **+1% net** under the retained scenario of 4 bps fee and 2 bps slippage per side. A separate **+1% price target for bearish exits only** is tested; that sensitivity preserves the bullish net-profit activation rule.',
'- Regime is the latest closed 1h Section5 REGIME direction. Entry-frozen Regime is also compared. Bullish DI+ comes from the most recent completed-5m preview of the forming hourly indicator. The prior exact kernel/parity checks remain applicable.',
'- Entry baseline: first decline from the forming-hour bearish spread peak above 40, with a known 5m DI-spread peak/drop at the same close or within the prior 10 minutes; enter next 5m open. DI− thresholds 40, 45 and 50 and optional RSI <20 are kept separate.',
'- Stops/targets are replayed on recorded 1m prices where available, with whole-trade 5m fallback. Low-first and high-first OHLC paths are reported as sensitivity scenarios, not tick-level certainty. Gap fills are retained rather than clipped to a loss cap.','',
'## Independent audit of the unexpectedly low winning ratio','',
 f"A separate first-barrier search checked **{a['independent_bearish_barrier_checks']}** unambiguous entry-frozen bearish trades. It independently calculated the hard-stop and target prices and searched for the first recorded minute/five-minute candle touching either. It found **{len(a['mismatches'])} mismatches** with the replay. One bar touching both levels was excluded from this agreement count.",
'',
'This validates the tested barrier ordering; it does not prove the entry definition captures every visually attractive dip. The core failure is buying before the downward move finishes: a later recovery does not undo an earlier protective stop. Diagnostic future labels were kept completely separate from the entry filters:','']
rows=[]
for t,s in r['stop_then_later_target'].items():rows.append([f'DI− >{t}',s['stopped_trades_with_complete_6h_window'],s['target_seen_in_a_later_5m_bar'],pct(s['pct'])])
lines += [table(['Baseline','Stopped trades, full 6h observation','Target touched in a later 5m bar','Share'],rows),'',
'These remain losing trades. Target touches in later bars are diagnostic labels, not instructions to remove or widen the stop.','',
'## Does the new bearish target fix it?','',
'Strict forming-1h + 5m DI-peak confluence, no optional RSI gate, non-overlapping positions, net-loss-budget stop:','']
rows=[]
for t in (40,45,50):
 item=v(t);s=low(item);old=low(item,'old_exit');rows.append([f'> {t}',s['closed'],pct(s['win_pct']),mean_range(item),pct(old['mean_net_pct']),num(s['median_holding_minutes'],1)+' min'])
lines += [table(['DI−','Closed trades','Winning ratio','Mean net, new target','Mean net, old trail¹','Median holding¹'],rows),'',
'¹ Low-first scenario. The new target changes payout after reaching profit, but cannot rescue entries that hit the stop first. For the pure bearish +1% / −0.5% net payoff, the simple break-even win rate is 33.33% before gap effects. The baselines remain below it.','',
'Cost/target-basis comparisons for the DI− >45 baseline:','']
rows=[]
for label,key in [('New exit, 0.5% net-loss budget','new_exit'),('New exit, literal 0.5% price stop','literal_price_stop'),('Bearish +1% price target; bullish unchanged','price_target_basis'),('Exit policy fixed to entry Regime','entry_regime_exit')]:
 s=low(v(45),key);rows.append([label,s['closed'],pct(s['win_pct']),pct(s['mean_net_pct']),pct(s['worst_net_pct'])])
lines += [table(['Scenario','Closed','Winning ratio','Mean net/trade','Worst modeled net'],rows),'',
'A literal 0.5% price stop loses about 0.60% net under the stated costs. The cost-adjusted stop is about 0.40045% below the paid entry fill; gap execution can still breach the intended budget. No loss is silently capped for presentation.','',
'## Causal breakout and crash observations','',
'These are recognition rules available at the close of the current 5m candle. They do not predict an unseen crash or declare a final swing extreme. All reference levels and denominators exclude the current candle:','',
 table(['Observation','Exact rule'],[
 ['Volume breakout','Close above the previous 12-bar high; bullish close in upper 30%; true range ≥1.2 × previous ATR(14); volume ≥1.5 × mean previous 20 bars.'],
 ['Volume breakdown','Close below previous 12-bar low; bearish close in lower 30%; true range ≥1.5 × previous ATR; volume ≥1.5 × prior mean.'],
 ['Rapid-breakdown / crash flag','Volume breakdown plus a decline ≥0.5% over 5m or ≥1% over 15m. This identifies an observed expansion, not a guaranteed future crash.'],
 ['Micro-high reclaim','Bullish close above the high of the previous three 5m bars, closing in the upper 40% of the current range.'],
 ['Range-low reclaim','Low breaks the previous 12-bar low, then the candle closes back above that known level, in the upper 35%, with relative volume ≥1.2.'],
 ['Breakout retest held','Within six bars after a volume breakout, low reaches or trades through the recorded level (a near-touch up to 0.05% above also qualifies), then closes above it in the upper 40%, with no fresh crash flag. The anchor never moves to a later range high.']]),'',
'The raw spot database stores base-asset volume; it is compared only with prior BTC base volumes. OHLCV comes from the existing Binance spot kline archive, following the [Binance kline contract](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market#klinecandlestick-data). Matching historical order-book liquidity was not invented.','',
'The source contains the following **flagged candles**, not that many independent market crashes or breakouts:','',
 table(['Flag','Five-minute candles','Fresh starts after >15m without same flag'],[[name,r['market_event_counts'][name],counts.get(name,'—')] for name in ('breakout_up','breakdown','crash','breakout_retest')]),'',
'`market_events.json.gz` retains every observed event with known time, prior range, relative volume and range/ATR. `event_review.json` groups repeated flags for review and lists the latest 50 starts; this grouping changes no entry or exit result.','']
review={}
for tag in ('crash','breakout_up','breakout_retest'):
 for e in [e for e in starts if tag in e['starts']][-2:]:review[e['time']]=e
rows=[]
for e in sorted(review.values(),key=lambda e:e['time']):
 link=f"[BTC 5m](http://localhost:8000/?symbol=BTCUSDT&interval=5m&at={e['time']})"
 rows.append([', '.join(e['starts']),e['time_pkt'],num(e['rvol']),num(e['tr_atr']),link])
lines += ['Examples known within the frozen observation window (chart links open the local app at that 5m candle):','',table(['Observed flag','Known at, PKT','Relative volume','TR / prior ATR','Review'],rows),'',
'## Did the execution filters help?','',
'The following rules were frozen in protocol.json before evaluation. Pending DI setups can wait at most six additional 5m candles (30 minutes) for price confirmation; a fresh crash cancels a pending entry. The confirmation price is the following open, not the earlier DI setup price.','',
'For DI− >45, strict confluence, no RSI gate:','']
rows=[]
for gate,label in [('immediate','Enter immediately'),('avoid_recent_crash','Veto crash now / previous 15m'),('avoid_unrecovered_crash','Veto unrecovered crash within 1h'),('wait_micro_reclaim','Wait for micro-high reclaim'),('wait_range_low_reclaim','Wait for range-low reclaim'),('wait_volume_breakout','Wait for volume breakout')]:
 s=low(v(45,gate));rows.append([label,s['closed'],pct(s['win_pct']),pct(s['mean_net_pct']),num(s['profit_factor']),s['periods']['2017_2023']['closed'],pct(s['periods']['2017_2023']['mean_net_pct']),s['periods']['2025_2026']['closed'],pct(s['periods']['2025_2026']['mean_net_pct'])])
lines += [table(['Entry rule','Trades','Winning ratio','Mean net','PF','2017–23 N','2017–23 mean','2025–26 N','2025–26 mean'],rows),'',
'Crash avoidance helps the strict setup modestly. It worsens the earlier/aggressive 5m entry family in this experiment, because high-volume selloffs include both continuing crashes and genuine exhaustion bounces. A generic “never buy after a crash flag” is not a demonstrated universal solution.',
'',
'The micro-high reclaim improves the DI− >45 baseline from about −0.131% to −0.090% per trade, but it remains negative. The volume-breakout subset is positive in only **seven trades**; it has six discovery trades, no 2024 validation trades, and its single 2025–26 trade loses. It is not a validated exception. No candidate meets the predefined discovery screen of ≥50 trades with positive expectancy and profit factor >1.',
'',
'Adding RSI <20 and comparing DI− >40 / >45 / >50 is included in results.json; it does not produce a supported, general-use profitable entry gate here.','',
'## Separate bullish breakout branch','',
'Breakouts are also tested as their own bullish entry family, without forcing an oversold DI− entry condition onto momentum entries. Both direct volume breakout and confirmed retest use the unchanged bullish profit-plus-DI+ trailing gate. A historical execution gap censors the full continuous account run; it is not silently closed to free capital. Later periods are therefore also tested separately, each explicitly starting flat:','']
rows=[]
for branch,item in r['breakout_branches'].items():
 for period in ('2017_2023','2024','2025_2026'):
  s=item['separate_flat_start_periods'][period]['low_first'];rows.append([branch,period,s['closed'],s['unresolved'],pct(s['win_pct']),pct(s['mean_net_pct']),num(s['profit_factor'])])
lines += [table(['Entry branch','Separate flat-start period','Closed','Unresolved','Winning ratio','Mean closed-trade net','PF'],rows),'',
'These are period-specific replays, not one combined compounded account return. Earlier source gaps remain censored. The later complete periods also have negative expectancy under the retained bullish exit gate, so the breakout label by itself is not sufficient to generate executable profitable buys.','',
'## What is usable now?','',
'- DI/spread exhaustion is a **watch condition** in this study. Price acceptance should be evaluated separately from pressure peaking.',
'- Volume-backed range breaks and rapid-breakdown flags are reproducible, causal **market-context observations**. They are useful for explaining and reviewing execution risk, but have not earned standalone BUY status.',
'- A micro-high reclaim is a testable entry-timing candidate; its modest improvement still falls short of positive expectancy.',
'- Keep the 0.5% protective budget and the declared regime-dependent exit policy. Do not manufacture a higher win rate by ignoring stops, retaining positions through unknown data, selecting the final low, or clipping losses.',
'- No feature or ADCN field is removed, and no live strategy is promoted. These results support further entry research rather than a deployable indicator.','',
'## Reproduction and integrity','',
'- `protocol.json`: predefined exit, phase-observation and validation rules; no parameter grid search.',
'- `results.json`: all 72 DI/RSI/entry-gate combinations, target/cost/Regime sensitivities, two OHLC orderings, three chronological periods, full execution traces and independent barrier audit.',
'- `five_minute_volumes.json.gz`: aligned frozen volume observations. Price source remains the same frozen 1h/5m archive used in v2. `execution_blocks.json.gz` freezes the minute/fallback blocks used for this replay.',
'- Run `PYTHONPATH=. .venv-build/bin/python3 Section_12_Research/reports/BTC_1h_bear_target_breakouts_v3/study.py`, then `.../write_report.py`.',
'- The 2025–26 window has already been viewed in earlier hypothesis work. It is a chronological check, not prospective validation. All positive tiny subsets and negative larger results remain reported.',
'- Verification: 28 targeted Section_13_Development/tests pass for exit-policy changes, bullish-gate preservation, stop priority, target basis, feature timing, prior-volume/range baselines, crash recovery, fixed retest anchors, missing data, delayed confirmation, intrabar reconstruction and original trailing behavior. The independent audit separately checked 328 unambiguous bearish first-barrier outcomes.','']
(P/'README.md').write_text('\n'.join(lines))
print(P/'README.md')
