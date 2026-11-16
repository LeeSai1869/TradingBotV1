"""Summarize the saved experiment without reading live databases."""
import csv
import gzip
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

OUT=Path(__file__).parent
PKT=ZoneInfo('Asia/Karachi')
def stamp(ms):return datetime.fromtimestamp(ms/1000,PKT).strftime('%d %b %Y %H:%M PKT')
def fmt(v,n=3):return '—' if v is None else f'{v:.{n}f}'


def main():
    lines=['# DI50 three-candle reversal — 15-minute spot study','',
           'The requested entry uses bearish same-timeframe Trend, a DI− peak and absolute DI-spread peak above 50, and the reverse DI+ trough. No RSI filter and no pivot labels select entries.','',
           'For closed candles 2 (two ago), 1 (previous), and 0 (confirmation):','',
           '```text','DI−[2] < DI−[1] and DI−[0] < DI−[1]','Spread[2] < Spread[1] and Spread[0] < Spread[1]','DI+[2] > DI+[1] and DI+[0] > DI+[1]','```','',
           'The primary threshold is DI−[1] >50 AND spread[1] >50. A separate version requires both values still above 50 on candle 0. The literal DI+[0] >= DI+[1] version is also separate; it happens to select the same BTC/SUI entries on these snapshots. No thresholds were optimized.','',
           '## Execution','',
           'BUY at the next contiguous 15m open. One position per coin. Net loss budget 0.5% from entry, including assumed costs. At each execution bar use only the latest closed 15m Regime and DI+: bearish Regime takes a fixed +1% net target; bullish Regime requires profit >=1% AND DI+ >50 to arm a permanent 0.5% trail below the highest raw price since entry. Neutral/unknown entry Regime is excluded and counted. While holding, unknown Regime cannot arm a new profit exit; hard/armed stops stay active. No fixed time exit.','',
           'Costs are assumed 4 bps fee plus 2 bps slippage per side. Prefer recorded complete 1m bars whose aggregate agrees with the stored 15m OHLC, otherwise 5m, otherwise explicitly labeled 15m. Low-first and high-first are different OHLC ordering assumptions, not guaranteed tick-path bounds. Actual adverse opening gaps are retained.','',
           '## Complete stored BTC/SUI research snapshots','',
           'These are stored measurements with complete historical Trend/Regime reconstructed previously by the current Section 5 definitions. This experiment did not rerun those classifiers. Feature generation/config and classifier source hashes were checked. This is not original live publication history. The partial live-memory pass is reported separately below.','',
           '| Coin / rule | Trades | Win rate: low / high first | Mean net/trade: low / high first | PF: low / high first |',
           '|---|---:|---:|---:|---:|']
    data={};trade_rows=[]
    names=[('peak_thresholds_with_plus','Peak >50 + DI+ trough'),('current_thresholds_with_plus','Still >50 + DI+ trough'),('peak_thresholds_without_plus','Peak >50, no DI+ turn filter')]
    for symbol in ['BTCUSDT','SUIUSDT']:
        with gzip.open(OUT/f'frozen_{symbol}_results.json.gz','rt') as f:r=json.load(f)
        data[symbol]=r
        for variant,label in names:
            paths=r['variants'][variant]['replays']['agreed_regime_exits'];a=paths['low_first']['summary'];b=paths['high_first']['summary']
            lines.append(f'| {symbol} · {label} | {a["closed"]} | {fmt(a["win_pct"],2)}% / {fmt(b["win_pct"],2)}% | {fmt(a["mean_net_pct"])}% / {fmt(b["mean_net_pct"])}% | {fmt(a["profit_factor"],2)} / {fmt(b["profit_factor"],2)} |')
        for t in r['variants']['peak_thresholds_with_plus']['replays']['agreed_regime_exits']['low_first']['trades']:
            trade_rows.append(dict(symbol=symbol,signal_known_pkt=stamp(t['signal_known_time']),entry_pkt=stamp(t['entry_time']),exit_upper_pkt=stamp(t['exit_time_upper']) if t['status']=='CLOSED' else '',entry=t.get('entry_fill'),exit=t.get('exit_reference'),net_pct=t.get('net_pct'),reason=t.get('reason',t['status']),execution_timeframe=t['execution_tf'],entry_regime=t['entry_regime'],arm_regime=t.get('arm_regime'),holding_minutes_upper=t.get('holding_minutes_upper')))
    lines+=['','Adding the DI+ reversal improves this sample substantially, but the primary rule has only 38 BTC and 11 SUI completed trades. Most BTC trades still lose under the low-first assumption. This does not support an “always good buy” claim or a validated deployment.','',
            'The threshold-at-confirmation version is much rarer: 3 BTC and 4 SUI completed trades. A current-only >50 filter should not be confused with buying after a >50 peak has already turned down.','',
            'Strict-rule median holding times under low-first: BTC 29 minutes; SUI 9 minutes. Maximums were 819 and 174 minutes respectively. These are exit-duration results, not imposed timeouts. Both source periods end at 14 November 2026, 18:15 PKT; BTC starts 17 August 2017 and SUI 3 May 2023.','',
            'A separate bearish-trailing sensitivity is retained in each result JSON; it does not replace the agreed bearish fixed target.','',
            '## Current stored-memory pass','']
    path=OUT/'memory_summary.json'
    if path.exists():
        memory=json.loads(path.read_text());good={s:r for s,r in memory.items() if r['status']=='complete'}
        total=sum(r['candles'] for r in good.values());known=sum(sum(r['indicator_funnel'].get('trend_'+d,0) for d in ('BEARISH','BULLISH','NEUTRAL')) for r in good.values())
        ready=sum(r['source'].get('memory',{}).get('feature_current',False) for r in good.values());valid=sum(r['indicator_funnel'].get('valid_feature_candles',0) for r in good.values())
        lines += [f'Read {len(good)} stored 15m coin scopes ({total:,} candles). Current feature formula is ready on {ready} scopes; {valid:,} candles have valid prices/current DI measurements. Usable Trend on those valid feature candles: {known:,} ({100*known/total:.2f}% of raw coverage). Missing Trend or unreplayed features are excluded, never treated as bearish or zero. Broad all-coin profitability is therefore not established by this incomplete pass.','',
                  '| Coin | Candles | Usable Trend candles | Strict peak-threshold entries | Closed | Win rate | Mean net/trade |','|---|---:|---:|---:|---:|---:|---:|']
        with (OUT/'memory_coverage.csv').open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['symbol','candles','usable_trend','trend_coverage_pct','strict_entries','strict_closed','strict_win_pct','strict_mean_net_pct'])
            for symbol,r in sorted(good.items()):
                n=sum(r['indicator_funnel'].get('trend_'+d,0) for d in ('BEARISH','BULLISH','NEUTRAL'));v=r['variants']['peak_thresholds_with_plus']
                writer.writerow([symbol,r['candles'],n,100*n/r['candles'],v['entries'],v['closed'],v['win_pct'],v['mean_net_pct']])
                lines.append(f'| {symbol} | {r["candles"]:,} | {n:,} | {v["entries"]} | {v["closed"]} | {fmt(v["win_pct"],2)}% | {fmt(v["mean_net_pct"])}% |')
        if len(good)!=len(memory):lines+=['',f'{len(memory)-len(good)} additional scopes failed to load; see memory_summary.json.']
    lines+=['','The reader timing bug was fixed: a runner refresh of a historical binding after candle reading began must not hide that already committed compatible prefix. The reader now observes the current binding while retaining the frozen market cutoff on the actual candle results. No stored indicators or pivots were changed.','',
            '## Previous DI values and workspace use','',
            'Memory contains `prev_di_plus` and `prev_di_minus`; labels are now **Previous DI+** and **Previous DI−**. They matched every checked preceding canonical measurement in the frozen cohorts. Previous absolute spread is `di.abs_spread` with candle=1; two-ago is candle=2. The editor now spells out **0=current, 1=previous, 2=two ago** for both comparison operands.','',
            'Six reviewable configurations are in `configs/`. The two strict-trough versions are also installed as workspace presets after validation. They use the new **Take profit** SELL action for the bearish 1% exit, and **Trailing SELL** for the bullish exit. Refresh the workspace, select the preset under **Start from**, then **Load strategy**. These presets reproduce the entry/exit conditions; the workspace currently uses selected-timeframe OHLC for execution, whereas this report uses finer stored 1m/5m prices. Their fills and returns can differ. No strategy was enabled for live trading.','',
            '## Evidence','',
            '- `protocol.json`: hypotheses, timing, exit policy and cost assumptions.','- `frozen_*_results.json.gz`: complete snapshot results, cases, both price-order paths and trailing sensitivity.','- `memory_summary.json` / `memory_coverage.csv`: partial all-coin coverage and results.','- `*_execution.json.gz`: frozen lower-timeframe prices used by this run.','- `independent_execution_audit.json`: independent fill arithmetic and price-bar checks.','- `strict_peak_trades.csv`: every primary strict-rule trade, including dates, returns and execution frame.','',
            '67 targeted unit/integration checks passed. The direct predicates matched the workspace expression evaluator at 4,980 checked BTC/SUI snapshot points, with zero mismatches. Independent arithmetic and stored-price-bar verification covered 1,516 closed execution checks with zero mismatches. Historical results remain exploratory; the recent-period samples are too small to establish reliability.']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n')
    with (OUT/'strict_peak_trades.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(trade_rows[0]));w.writeheader();w.writerows(trade_rows)


if __name__=='__main__':main()
