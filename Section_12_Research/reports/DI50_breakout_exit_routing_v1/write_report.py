"""Reviewable diagnostics; no outcome-dependent strategy fitting."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))

from collections import Counter
import csv
from datetime import datetime
from statistics import median
from zoneinfo import ZoneInfo
from . import study as s

ZONE=ZoneInfo('Asia/Karachi')
FEATURES=('relative_volume','natr_pct','candle_range_atr','close_position','lower_wick_fraction','plus_rise','minus_drop','close_to_ema50_pct')
LABELS=('EXTENDED_2PCT','ORDINARY_REBOUND','FAILED_BEFORE_0_5','CENSORED')


def date(t):return datetime.fromtimestamp(t/1000,ZONE).isoformat()


def csv_file(name,rows):
    with (s.OUT/name).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    diagnostics={};exports=[];case_rows=[];lines=[]
    for symbol in ('BTCUSDT','SUIUSDT'):
        r=s.read(s.OUT/f'{symbol}_results.json.gz');observations=s.read(s.OUT/f'{symbol}_5m_observations.json.gz');cases={c['entry_time']:c for c in r['cases']}
        old=r['results']['old_regime_reference'];losers=[c for c in r['cases'] if c['original']['reason']=='HARD_STOP']
        after={}
        for minutes in ('15','30','60','240'):
            windows=[c['post_stop']['horizons'][minutes] for c in losers];complete=[w for w in windows if w['complete']]
            after[minutes]=dict(complete=len(complete),incomplete=len(windows)-len(complete),hit_0_5=sum(w['reached_0_5_gross'] for w in complete),hit_1=sum(w['reached_1_gross'] for w in complete))
        stats={}
        for label in LABELS:
            selected=[c for c in r['cases'] if c['labels']['low_first']==label]
            stats[label]=dict(count=len(selected),features={})
            for feature in FEATURES:
                values=[c['features'][feature] for c in selected if c['features'][feature] is not None]
                stats[label]['features'][feature]=dict(count=len(values),median=median(values) if values else None,min=min(values) if values else None,max=max(values) if values else None)
        routing={};periods={};comparison_rows=[]
        for name,paths in r['results'].items():
            lo=paths['low_first']['summary'];hi=paths['high_first']['summary']
            comparison_rows.append(f"| {name} | {lo['wins']}/{lo['closed']} · {lo['win_pct']:.2f}% / {hi['win_pct']:.2f}% | {lo['mean_net_pct']:+.3f}% / {hi['mean_net_pct']:+.3f}% | {lo['profit_factor']:.2f} / {hi['profit_factor']:.2f} | {lo['selected_breakouts']} |")
            if name.startswith('hybrid'):
                routing[name]={}
                for order,payload in paths.items():
                    ts=payload['trades'];selected=[t for t in ts if t.get('selected_breakout')];target=r['policies'][name]['target']
                    quick=r['results']['fixed_0_5_gross' if target==.5 else 'fixed_1_gross'][order]['trades'];baseline={t['entry_time']:t for t in quick}
                    counts=Counter(cases[t['entry_time']]['labels'][order] for t in selected)
                    routing[name][order]=dict(selected=len(selected),selected_labels=dict(counts),missed_extended=sum(c['labels'][order]=='EXTENDED_2PCT' and c['entry_time'] not in {t['entry_time'] for t in selected} for c in r['cases']),
                                             wins_to_loss=sum(baseline[t['entry_time']]['net_pct']>0 and t['net_pct']<0 for t in ts),loss_to_win=sum(baseline[t['entry_time']]['net_pct']<0 and t['net_pct']>0 for t in ts),
                                             net_pct_added_vs_quick=sum(t['net_pct']-baseline[t['entry_time']]['net_pct'] for t in ts))
            split=2022 if symbol=='BTCUSDT' else 2025
            periods[name]={}
            for label,condition in ((f'through_{split}',lambda y:y<=split),(f'after_{split}',lambda y:y>split)):
                periods[name][label]={order:s.summaries([t for t in payload['trades'] if condition(datetime.fromtimestamp(t['entry_time']/1000,ZONE).year)]) for order,payload in paths.items()}
            for order,payload in paths.items():
                for t in payload['trades']:
                    proof=t.get('breakout_evidence') or {}
                    exports.append(dict(symbol=symbol,policy=name,order=order,entry_pkt=date(t['entry_time']),exit_pkt_upper=date(t['exit_time_upper']),entry_open=t['entry_open'],exit_reference=t['exit_reference'],net_pct=t['net_pct'],gross_pct=100*(t['exit_reference']/t['entry_open']-1),reason=t['reason'],execution_tf=t['execution_tf'],selected_breakout=t.get('selected_breakout',False),selection_pkt=date(proof['selected_at']) if 'selected_at' in proof else '',proof_known_pkt=date(proof['known']) if proof.get('known') is not None else '',armed=t['armed'],protected=t.get('protected',False),label=cases[t['entry_time']]['labels'][order]))
        obs_at_entry=[]
        for c in r['cases']:
            values=observations[str(c['entry_time'])]['values'];point=next((p for p in reversed(values) if p['known']<=c['entry_time'] and c['entry_time']-p['known']<s.STEP5),{})
            obs_at_entry.append(point)
            result=dict(symbol=symbol,entry_pkt=date(c['entry_time']),signal_index=c['signal_index'],label_low_first=c['labels']['low_first'],label_high_first=c['labels']['high_first'],execution_tf=c['execution_tf'],old_reason=c['original']['reason'],old_net_pct=c['original']['net_pct'],old_max_gross_pct=100*(c['original']['highest']/c['original']['entry_open']-1),entry_5m_ready=bool(point.get('ready')),entry_crash_unrecovered=point.get('crash_unrecovered',False),**c['features'])
            for name in ('fixed_0_5_gross','fixed_1_gross','hybrid_0_5_volume_breakout','hybrid_1_volume_breakout','hybrid_0_5_micro_reclaim'):
                t=next(t for t in r['results'][name]['low_first']['trades'] if t['entry_time']==c['entry_time']);result[name+'_net_pct']=t['net_pct'];result[name+'_selected']=t.get('selected_breakout',False)
            for m in ('15','30','60','240'):
                h=c['post_stop']['horizons'][m] if c['post_stop'] else {}
                for field in ('complete','reached_0_5_gross','reached_1_gross'):result[f'post_stop_{m}m_{field}']=h.get(field)
            case_rows.append(result)
        differences=[dict(entry_pkt=date(a['entry_time']),execution_tf=a['execution_tf'],low_net=a['net_pct'],high_net=b['net_pct']) for a,b in zip(old['low_first']['trades'],old['high_first']['trades']) if abs(a['net_pct']-b['net_pct'])>1e-8]
        diagnostics[symbol]=dict(entries=r['entries'],labels=stats,old_losses=len(losers),old_losers_reached_0_5_before_stop=sum(c['original']['highest']>=c['original']['entry_open']*1.005 for c in losers),old_losers_reached_1_before_stop=sum(c['original']['highest']>=c['original']['entry_open']*1.01 for c in losers),post_stop=after,routing=routing,periods=periods,old_order_differences=differences,
                                 entry_5m_usable=sum(p.get('ready',False) for p in obs_at_entry),entry_crash_flags=sum(p.get('crash_unrecovered',False) for p in obs_at_entry),observation_counts=dict(total=sum(len(v['values']) for v in observations.values()),ready=sum(p['ready'] for v in observations.values() for p in v['values'])))
        lines.extend([f'## {symbol} — {r["entries"]} identical entries','',f'Period: {date(r["first"])} to {date(r["last"])}. Execution: {r["common_execution_frames"]}.','',
                      '| Exit policy | Wins low-first · win% low / high | Mean net/trade low / high | PF low / high | Routed low |','|---|---:|---:|---:|---:|',*comparison_rows,'',
                      f'Original hard stops: {len(losers)}. Of those, {diagnostics[symbol]["old_losers_reached_0_5_before_stop"]} reached +0.5% gross before the stop, and {diagnostics[symbol]["old_losers_reached_1_before_stop"]} reached +1% gross. A later recovery does not reverse the filled stop.','',
                      '| After the original stop | Complete observations | Reached entry +0.5% | Reached entry +1% |','|---|---:|---:|---:|',
                      *[f'| {m} minutes | {v["complete"]} | {v["hit_0_5"]} | {v["hit_1"]} |' for m,v in after.items()],'',
                      '| Entry feature median | Extended ≥2% | Ordinary rebound | Failed before +0.5% |','|---|---:|---:|---:|',
                      *[f'| {feature} | '+ ' | '.join(f'{stats[label]["features"][feature]["median"]:.3f}' for label in LABELS[:3])+' |' for feature in FEATURES],'',
                      f'Class counts: {dict(Counter(c["labels"]["low_first"] for c in r["cases"]))}. These are future diagnostic labels, not inputs to the router. Class definitions use the original initial stop, no artificial time exit.',
                      f'All {diagnostics[symbol]["entry_5m_usable"]}/{r["entries"]} entries have compatible closed 5m measurements. The strict crash diagnostic flagged {diagnostics[symbol]["entry_crash_flags"]} at entry; this supplies no evidence that it can remove these losses.',''])
    s.save(s.OUT/'diagnostics.json',diagnostics);csv_file('all_exit_trades.csv',exports);csv_file('case_diagnostics.csv',case_rows)
    header='''# DI50: ordinary rebounds versus breakout trailing exits

**Cost assumption superseded:** this historical run used approximately 0.12% total costs. The user specifies **0.2% total round-trip costs**, so +0.5% gross gives +0.3% net. Use the [corrected cost comparison](../DI50_breakout_exit_routing_cost20bps/README.md) for current results. The tables below retain the original run for auditability.

The same 38 BTC and 11 SUI strict bearish-Trend 15m entries are retained. This is an exit experiment, not a new entry strategy. The eight rows in the earlier partial-memory table were eight coins, not the lifetime trade count. The strict simultaneous DI peaks/DI+ trough are rare; these counts do not count every market pivot or 1% move.

## What changed and what the evidence supports

Ordinary exits are now explicitly **+0.5% or +1% gross chart-price gain** from the raw next-open entry. Under the assumed 4 bps fee and 2 bps slippage per side, they net **+0.37947%** and **+0.87887%**. The prior +1% target was net; its equivalent raw price rise is about 1.1213%. Every entry retains the initial 0.5% net-loss stop. No fixed holding timeout, stop removal, discarded loss or future-known classification is used.

The +0.5% gross exit raises BTC win rate to 50.0% under low-first, but its average net return is **−0.0603%**. Its break-even win rate is about **56.85%**, assuming every loss is exactly −0.5%. More wins alone do not make it profitable. SUI rises to 54.55% and also remains slightly negative under that path. The +1% gross control yields BTC 36.84% wins and +0.0080% mean net; SUI 45.45% and +0.1268%.

The main predefined breakout gate requires a closed **5m candle above the prior 12 highs**, bullish, closing in its top 30%, **relative volume ≥1.5** and **range/ATR ≥1.2**; the next execution open must hold the broken level. If known before the ordinary target exits, it switches permanently to a trail: +1% gross arms a stop 0.5% below the highest price since entry. No extra Regime/DI+ activation restriction is used for this new experimental branch. The old regime-dependent policy is retained separately as a reference.

For BTC with a +1% ordinary target, that gate selects 5/38 trades: **2 extended moves, 1 ordinary rebound, 2 immediate failures**. Two trail winners return +1.678% and +3.000% net; three selections stop at −0.5%. Mean net across all 38 is +0.0849% / +0.1147% for low/high first, compared with +0.0851% / +0.1640% under the old policy. It is a candidate for further observation, with no demonstrated advantage over the old policy. It misses 5 of the 7 extended BTC moves and selects no SUI trade. It is not a general breakout classifier.

At a +0.5% ordinary target, BTC switches only 3 trades: the +3.000% runner and two losses. The +0.5% target often fills **before** the later 5m breakout confirmation is available. Its tiny positive mean (+0.0087% low-first) is driven by one runner. Removing that one runner's incremental benefit leaves the plain quick-exit result negative.

The weaker 5m prior-three-high reclaim catches more moves, but also 11 of BTC's 19 failures before +0.5%. It is too broad as a stand-alone quality filter. On SUI it helps this 11-trade sample, which is insufficient to establish reliability. The 15m entry expansion filter also selects both runners and failures; higher entry volume/range alone does not separate them. BTC extended moves have stronger median entry volume and DI recovery than ordinary rebounds, but failed entries are also high-volume/high-range. SUI does not reproduce BTC's volume separation. These descriptive medians are exploratory, not fitted thresholds.

## Why the old BTC win rate was only 34.21–39.47%

In low-first, 25/38 BTC entries hit the initial stop. **Only 6 of those 25 reached +0.5% gross beforehand**; taking +0.5% saves those six, but the other 19 still stop first. Of the 25 stopped trades, 7 later reach entry +1% within four hours. That later recovery does not change the actual stopped trade. Two trades contain both stop and target within a recorded **1m bar**; changing assumed within-minute order changes 13 wins to 15 and explains the 34.21% versus 39.47% range. The dates and both paths are retained in diagnostics.json.

The original low-first BTC wins average about +1.21% net while losses are −0.5%, so a low hit rate can still produce positive historical expectancy. That does not establish future profitability. A strict “no losing exit” rule is incompatible with retaining these same entries and the mandatory initial stop. Entry timing/selection must improve to reduce the 19 failures that never first earn +0.5%. Waiting indefinitely for recovery would silently abandon the loss limit.

The net-breakeven sensitivity only raises protection **after an observed +0.5% gross crossing** on a selected breakout trade. It changes no outcomes for the volume gate here: its false positives stop before earning that protection. Breakevens are counted separately from wins; adverse gaps would remain real losses.

## Timing, source quality and limitations

Entry predicates, source hashes and historical context are exactly the previous frozen study. Stored 15m measurements use the already reconstructed Section 5 context, not original live publication history. This experiment does not rerun indicators or change Trend/Regime. Only the requested stored 5m measurements are additionally read; no ADCN/features are pruned. The all-coin live-memory pass remains incomplete and is not pooled into this complete-cohort comparison.

Routing uses only a last-closed 5m observation known at the **execution bar open**, never the close of the minute containing a target/stop. A future breakout cannot retroactively cancel a filled quick exit. All 49 entries have usable 5m measurements at entry; warm-up/unavailable observation rows do not fire gates. Missing observations fall back to the ordinary target. Gate observations, memory provenance, execution candles and every losing trade are frozen in this folder.

Each entry uses a common execution frame across every compared policy, chosen for continuous matching prices, not favorable returns: 47 entries use 1m and 2 use 5m. Low-first and high-first are explicit OHLC assumptions, **not guaranteed bounds**; trailing results can be better under low-first than high-first. There is no tick-level execution, queue model or proof of fills at real order size. Costs are assumptions.

Predefined gates and all variants are shown below. Chronological sensitivities are in diagnostics.json, not an untouched holdout. BTC's main +1% volume hybrid is positive in both through-2022 and 2023+ slices (+0.1290% on 21 trades and +0.0303% on 17), but SUI's +1% control is negative through 2025 and positive in its four 2026 trades. There are only 49 total entries and 11 extended-move labels. No universal classifier or deployment claim follows.

Research only: no live trading rules, chart settings, runner services or orders changed. Keep the volume-backed gate as a BTC research candidate, retain the DI+ turn for the present entry hypothesis, and do not remove features from Memory based on this sample.

'''
    footer='''## Reproduce and inspect

- `protocol.json`: definitions frozen before outcome inspection.
- `summary.json`: all policies and both paths.
- `diagnostics.json`: routing errors, class feature distributions, post-stop recoveries, periods and ambiguity.
- `case_diagnostics.csv`: all 49 opportunities and diagnostic labels.
- `all_exit_trades.csv`: all 1,176 policy/path trades, fees included, no omitted losses.
- `*_5m_observations.json.gz` and `*_execution.json.gz`: frozen gate evidence and price bars.
- `independent_execution_audit.json`: 1,078 new exit replays through a separate segment engine plus 98 unchanged original trades, zero mismatches. Gate observations are frozen inputs, not an independently recalculated indicator audit.

29 targeted tests passed, including gross/net conversion, closed-bar timing, future-signal rejection, same-bar protection order, unchanged initial stops, retained adverse gaps and missing post-stop coverage.

```sh
PYTHONPATH=/tmp/btc-section5-test-deps:. .venv-build/bin/python3 -m research_reports.DI50_breakout_exit_routing_v1.study
PYTHONPATH=/tmp/btc-section5-test-deps:. .venv-build/bin/python3 -m research_reports.DI50_breakout_exit_routing_v1.audit_results
PYTHONPATH=/tmp/btc-section5-test-deps:. .venv-build/bin/python3 -m research_reports.DI50_breakout_exit_routing_v1.write_report
```

Re-running the study reads current stored 5m memory; that memory generation may later differ. Auditing/reporting the frozen artifacts does not read new market values.
'''
    (s.OUT/'README.md').write_text(header+'\n'.join(lines)+footer)
    print('Wrote README, diagnostics and all trade/case CSVs.')


if __name__=='__main__':main()
