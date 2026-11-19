"""Human-readable audit of the user's protective-stop/trailing policy."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))

import json,gzip,hashlib
from datetime import datetime,timezone,timedelta
from pathlib import Path
P=Path(__file__).parent
hour=json.loads((P/'results.json').read_text());intr=json.loads((P/'intrabar_results.json').read_text());parity=json.loads((P/'five_minute_parity.json').read_text())
def n(x,d=2):return '—' if x is None else f'{x:.{d}f}'
def pc(x,d=2):return n(x,d)+'%' if x is not None else '—'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join('---' for _ in headers)+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])
def stats(v,policy='net_loss_budget',order='low_first'):return v['replays'][policy][order]['single_position']
def rng(v,key,policy='net_loss_budget',d=3):
 a=stats(v,policy,'low_first')[key];b=stats(v,policy,'high_first')[key]
 if a is None or b is None:return '—'
 return f'{min(a,b):.{d}f} to {max(a,b):.{d}f}'
lines=['# BTC 1h / 5m confirmation: 0.5% protection and regime-dependent trailing','','**Later policy revision:** see the [fixed bearish +1% target, breakout and crash audit](../BTC_1h_bear_target_breakouts_v3/README.md). The bearish trailing results below remain a historical comparison.','',
'13 November 2026, Asia/Karachi. This replaces the previous report’s fixed-target / 24-hour headline experiment with the user’s actual protective-stop and trailing policy. Research only; no live rules, indicator formulas, settings, orders or production feature memory changed.','',
'## What was wrong with the earlier headline?','',
'The earlier headline measured whether a +1% target arrived within 24 hours, with unresolved positions marked to market at that horizon. A separate 0.5% stop sensitivity existed, but the headline did not implement the user’s regime-dependent trailing exit. Its “recent example worked” statement therefore does not establish that the example survives the specified stop.','',
'Its strict count required an hourly local spread peak above 40, spread **still above 40** after the hourly drop, DI− **still above** the threshold, and RSI below 20 at that confirmation close. For DI− >40 this produced **135 raw signals**, of which **134** had a complete 24-hour observation window. That was not the total number of dips or potential intrabar entries.','',
'## Exact revised rules','',
'1. Spot only. The intended loss limit applies from entry on every trade: an immediate protective stop is present while waiting for profit/trailing conditions. No averaging down, fixed 1% sale, or 24-hour exit is added.',
'2. In **bearish Regime**, profit ≥1% activates trailing. In **bullish Regime**, activation requires **profit ≥1% AND DI+ >50**, as explicitly confirmed by the user. Once armed, keep it armed.',
'3. The trailing stop is **0.5% below the highest observed price since BUY**, including any high before activation. A late activation already below that stop exits at the current price rather than an invented better fill.',
'4. Regime comes from the latest completely closed hourly Section 5 REGIME output, reconstructed offline from the current definitions. In the intrabar Section_13_Development/tests, DI+ for bullish activation comes from the latest 5m-confirmed preview of the forming hourly indicator. Unknown/neutral entry regimes are counted and skipped; an existing protective/armed stop remains active.',
'5. Costs retain the earlier scenario: **4 bps fee + 2 bps slippage per side**. “Profit ≥1%” in the main test means net of those costs. A separate 1% price-appreciation sensitivity is recorded in the closed-hour results.',
'6. A literal 0.5% price stop from the paid entry fill returns approximately **−0.59945% net** under these costs. To respect an intended **−0.5% net** budget, the cost-adjusted scenario places the hard stop about **0.40045%** below the entry fill. Both interpretations are reported. Real gap-opening fills are retained, not clipped to force the limit.',
'7. Reaching exactly +1% net and then falling 0.5% from that peak leaves approximately **+0.495% net**, rather than locking in +1%. Further gains can increase the trailing exit. This is ordinary multiplicative trailing behavior; see the [Binance trailing-stop FAQ](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/trailing-stop-faq.md).','',
'## How the forming-hour / 5m check works','',
'The user proposed a high on the 5m chart as intrabar confluence. This report interprets that as a **5m DI-spread high and its first decline**, not a future price-pivot label. Three causal timing definitions are kept separate:','',
'- **Forming-hour first drop:** evaluate the developing 1h DI/RSI at each closed 5m candle; buy at the next 5m open after its bearish spread peaks above 40 and starts declining.',
'- **Forming-hour drop + 5m peak (strict confluence):** the above hourly preview turn plus a confirmed bearish 5m DI-spread peak/drop known at the same close or within the preceding 10 minutes. No additional “5m spread >40” threshold is invented.',
'- **Earlier 5m confirmation:** the forming 1h DI− and bearish spread are still above the selected threshold / 40, and the 5m DI-spread peak turns down. This can enter before the forming hourly spread itself turns; it is a distinct, earlier alternative, not silently substituted for the original condition.',
'- Local peaks use only known values, including plateaus after an observed rise. Flat stretches after a decline do not fabricate new peaks. The future final hourly high/low is never used to choose an entry.',
'- Entry is the next 5m open. Stops and trailing execute using recorded **1m candles** where available, rerunning the entire trade on **5m** when 1m data is missing. Two explicit OHLC orderings are tested: open→low→high→close and open→high→low→close. These are sensitivity scenarios, not guaranteed tick-level bounds.','',
'## Counts and results','',
'The frozen archive contains **80,884 hourly candles**, 2017-08-17 through 2026-11-13, with stored RSI(7) and DI/ADX length 10. The confirmed-hour funnel had **10,293 bearish local spread first drops**; only **370** followed a spread peak above 40. Moving to 5m-confirmed forming-hour observations changes the count substantially:','']
rows=[]
for t in (40,45,50):
 h=hour['variants'][f'di_minus_gt{t}_peak_no_rsi'];a=intr['variants'][f'forming_hour_first_drop_di_minus_gt{t}_rsi_none'];b=intr['variants'][f'forming_hour_drop_with_5m_peak_di_minus_gt{t}_rsi_none'];c=intr['variants'][f'forming_hour_extreme_with_5m_peak_di_minus_gt{t}_rsi_none'];rows.append([f'> {t}',h['raw_setups'],a['raw_setups'],b['raw_setups'],c['raw_setups']])
lines += [table(['DI−','Closed-hour peak/drop','Forming-hour first drop','Strict 1h + 5m confluence','Earlier 5m confirmation'],rows),'',
'Counts above omit an RSI gate. They are raw setups, not independent trades; the one-position replay suppresses signals while already holding. DI− thresholds in the first two turn-based methods are checked at the observed peak. RSI <20 is separately compared at the peak and at confirmation.','',
'**Strict confluence, 0.5% net-loss-budget stop, no RSI gate:**','']
rows=[]
for t in (40,45,50):
 v=intr['variants'][f'forming_hour_drop_with_5m_peak_di_minus_gt{t}_rsi_none'];s=stats(v);rows.append([f'> {t}',v['raw_setups'],s['closed'],rng(v,'win_pct',d=1)+'%',rng(v,'mean_net_pct')+'%',n(s['profit_factor']),n(s['median_holding_minutes'],1)+' min'])
lines += [table(['DI−','Raw setups','Closed non-overlapping trades¹','Winning trades','Mean net/trade²','Profit factor³','Median holding⁴'],rows),'',
'¹ Trade counts use the low-first scenario; the audit retains both scenarios. ² Range spans the two modeled OHLC orderings. ³ Low-first scenario. ⁴ Holding times are upper bounds rounded to the end of the execution candle. No fixed holding period is imposed.','',
'**The same strict confluence with RSI <20 at signal confirmation:**','']
rows=[]
for t in (40,45,50):
 v=intr['variants'][f'forming_hour_drop_with_5m_peak_di_minus_gt{t}_rsi_signal'];s=stats(v);rows.append([f'> {t}',v['raw_setups'],s['closed'],rng(v,'win_pct',d=1)+'%',rng(v,'mean_net_pct')+'%',n(s['median_holding_minutes'],1)+' min'])
lines += [table(['DI−','Raw setups','Closed trades','Winning trades','Mean net/trade','Median holding'],rows),'',
'**Earlier 5m confirmation while the forming hour remains extreme, no RSI gate:**','']
rows=[]
for t in (40,45,50):
 v=intr['variants'][f'forming_hour_extreme_with_5m_peak_di_minus_gt{t}_rsi_none'];s=stats(v);rows.append([f'> {t}',v['raw_setups'],s['closed'],rng(v,'win_pct',d=1)+'%',rng(v,'mean_net_pct')+'%',n(s['median_holding_minutes'],1)+' min'])
lines += [table(['DI−','Raw setups','Closed trades','Winning trades','Mean net/trade','Median holding'],rows),'',
'The 5m confluence improves expectancy relative to waiting for the hourly close, but **all tested combinations remain negative after costs**. Requiring RSI below 20 reduces entries without establishing a profitable version. The dominant failure is stopping out before the rebound or before the trailing activation gate. Bigger DI− thresholds do not repair this.',
'', 'A separate literal 0.5% price-stop scenario is also negative across these conditions. For strict confluence without RSI, its mean net results are:','']
rows=[]
for t in (40,45,50):
 v=intr['variants'][f'forming_hour_drop_with_5m_peak_di_minus_gt{t}_rsi_none'];s=stats(v,'price_stop');rows.append([f'> {t}',s['closed'],rng(v,'mean_net_pct','price_stop')+'%',n(s['median_holding_minutes'],1)+' min',pc(s['worst_net_pct'])])
lines += [table(['DI−','Closed trades','Mean net/trade','Median holding','Worst modeled net loss'],rows),'',
'## What happened to the recent example?','',
'The previous 10:00 PKT closed-hour entry on 13 November later reached the 1% target, but **it stopped out first** under the revised risk rules. Its paid entry reference was 68,594.80; the literal price stop was 68,251.82, reached during 10:55–11:00 PKT. The cost-adjusted net-budget stop was 68,320.11, reached during 10:00–10:05 PKT. The later target touch is irrelevant after exiting. The minute archive ends before this date, so this specific execution uses the recorded 5m fallback.','',
'Forming-hour / 5m entries are different timestamps; all individual entry evidence and their own stop/activation paths are stored in intrabar_results.json. No winning label from the old fixed-target study is carried into this trailing replay.','',
'## Integrity, coverage and practical limits','']
q=intr['data_quality']
lines += [f"- Hourly kernel replay reproduced **{q['closed_hour_kernel_parity']['compared']:,}** stored DI/RSI points with maximum error **{q['closed_hour_kernel_parity']['max_abs_error']}**. Forming previews at the final 5m close reproduced **{q['terminal_preview_parity']['compared']:,}** frozen hourly points with maximum error **{q['terminal_preview_parity']['max_abs_error']}**.",
 f"- The source contains **{q['raw_5m_candles']:,}** recorded 5m candles. **{q['matching_hour_count']:,}** hourly aggregates match the frozen hourly OHLC; **{q['incomplete_or_mismatched_hour_count']}** incomplete/mismatched hours were excluded from intrabar setup reconstruction. They were not repaired or substituted.",
 f"- The 5m DI/RSI calculation matched **{parity['compared']}** deterministic stored feature checkpoints, maximum error **{parity['max_abs_error']}**. Intermediate 1h previews always reuse the prior closed-hour smoothing state; they never advance the hourly recurrence twelve times.",
'- Neutral/unknown entry regimes and source mismatches are counted separately. The closed-hour comparison contains one early 2017 minute/5m opening price inconsistent with its frozen hourly opening price; that entry was excluded rather than forced into a fill. Intrabar setups exclude mismatched hours up front.',
'- A gap can exceed an intended loss cap. In the earlier-5m DI− >40 scenario, two entries breached the cost-adjusted −0.5% budget on modeled opening gaps; the worst was about −0.6163% net. These losses remain in the report. The strict-confluence scenarios had no modeled net-budget breach in this sample.',
'- A small intrabar stop or trailing reversal can still have an unknown tick sequence inside a one-minute candle. The audit flags same-bar cases and shows both ordering scenarios; it does not claim execution precision unavailable from OHLC.',
'- All model selection is retrospective research. The newest 5m-confluence idea was motivated by already viewed charts, so these results do not constitute a prospective validation. No profitable exception is selected from a small regime/date subset.',
'- The research uses current Section5 definitions replayed offline. This is reconstructed availability, not proof the service published every historical classification at that time. Production history recovery was not changed for this test.','',
'## Files and verification','',
'- `results.json`: the confirmed-hour comparison, all thresholds/RSI timings, price-stop/net-budget/activation/current-vs-entry-Regime sensitivities, independent and one-position outcomes, and entry traces.',
'- `intrabar_results.json`: all 27 forming-hour / 5m confirmation / RSI combinations, both cost-budget interpretations and OHLC ordering scenarios, setup counts and per-entry evidence.',
'- `five_minute_source.json.gz`: frozen recorded 5m OHLC. `execution_blocks.json.gz` and `intrabar_execution_blocks.json.gz`: frozen indexed minute/fallback price blocks used for exits.',
'- `five_minute_parity.json`: indexed stored-feature comparison. The original frozen hourly measurements remain in `../BTC_1h_di_spread_reversal/source.json.gz`.',
'- Reproduce: `PYTHONPATH=. .venv-build/bin/python3 Section_12_Research/reports/BTC_1h_di_spread_trailing_v2/replay.py`, then `.../intrabar_5m.py`, then `.../write_report.py`. Cached price blocks allow repeated replays without re-reading the corresponding market rows.',
'- Verification: 18 targeted tests cover protective stops from entry, fee-adjusted budgets, bearish/bullish activation, no fixed-target exit, trailing highs before/after activation, late activation market fills, opening gaps, time availability, signal filter timing, OHLC ordering, unresolved capital and intrabar kernel/plateau behavior.',
'', 'Treat this as an exhaustion-watch condition pending a better entry filter. The specified 0.5% protection and trailing logic have now been tested explicitly; they do not make this entry hypothesis profitable on their own.','']
(P/'README.md').write_text('\n'.join(lines));print(P/'README.md')
