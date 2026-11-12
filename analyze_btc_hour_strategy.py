"""Replay configurable BTC 1h AND/OR branches over every stored closed candle."""
import argparse
from datetime import datetime
import gzip
import json
from pathlib import Path
import sqlite3

from Section_1_Global_Core import btc_hour_sequence_source
from Section_8_Decision_Engine import strategy_analyzer as analyzer


def read(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)


def save(path, value):
    data = (json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if path.suffix == '.gz':
        data = gzip.compress(data, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    temporary.write_bytes(data)
    temporary.replace(path)


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('Include an explicit timezone, e.g. 2025-01-01T00:00:00Z')
        return int(parsed.timestamp() * 1000)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def visual(report):
    """Offline inspector, including full signal/trade lists and failed-cohort comparisons."""
    data = json.dumps(report, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>BTC 1h strategy analyzer</title><style>body{font:15px system-ui;background:#121b28;color:#e1e7ef;max-width:1400px;margin:auto;padding:16px;overflow-wrap:anywhere}select,button{padding:7px;max-width:100%}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{padding:6px;text-align:left;border-bottom:1px solid #405067}.scroll{overflow:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>
<h1>BTC 1h strategy analyzer</h1><p>Every closed candle; multiple AND/OR branches; oldest qualifying BUY, then oldest qualifying SELL. Starts flat. Next-open fills with fees/slippage. Research only; live trading is unchanged.</p>
<h2>Complete chronological replay</h2><pre id="summary"></pre>
<h2>Chronological results</h2><p>Closed trades by exit-fill UTC year; state is carried across years. Not an untouched holdout. Compounding and drawdown below include completed trades only.</p><div class="scroll"><table id="years"></table></div>
<h2>Branches and missing inputs</h2><p>Raw matches include same-side duplicates suppressed by the alternating state. Missing-field counts can overlap; an OR expression may resolve true despite another missing operand.</p><div class="scroll"><table id="branches"></table></div>
<h2>Trades and revision diagnostics</h2><label>View <select id="view"><option value="trades">All trades</option><option value="wins">Successful trades</option><option value="failures">Failed trades</option><option value="unresolved">Open/censored</option></select></label>
<label>Entry UTC year <select id="year"><option>ALL</option></select></label>
<button id="prev">Previous 50</button><button id="next">Next 50</button><span id="page"></span>
<div class="scroll"><table id="trades"></table></div><pre id="detail"></pre>
<h2>Accepted BUY/SELL signals</h2><button id="signal-prev">Previous signals</button><button id="signal-next">Next signals</button><p id="signal-count"></p><div class="scroll"><table id="signals"></table></div>
<details><summary>Configuration, baseline comparison, full signals and input provenance</summary><pre id="config"></pre></details>
<script>const d=__REPORT__,el=(tag,text,parent)=>{const n=document.createElement(tag);n.textContent=text;parent.append(n);return n},by=id=>document.getElementById(id),stamp=v=>v===null||v===undefined?'unavailable':new Date(v).toISOString(),fmt=v=>v===null||v===undefined?'unavailable':Number(v).toFixed(3);let page=0,signalPage=0;
by('summary').textContent=JSON.stringify({strategy:d.config.id,summary:d.summary,accepted_BUY:d.signals.filter(s=>s.side==='BUY').length,accepted_SELL:d.signals.filter(s=>s.side==='SELL').length,invalid_price_candles:d.invalid_price_candles,price_gaps:d.price_gaps,unavailable_feature_fields:d.unavailable_feature_fields,revision_comparison:d.comparison?.counts||'No baseline supplied'},null,2);
function table(id,heads,rows){const t=by(id);t.replaceChildren();let h=el('tr','',t);heads.forEach(v=>el('th',v,h));rows.forEach(row=>{let tr=el('tr','',t);row.forEach(v=>el('td',v,tr))});}
table('years',['UTC year','Closed','Wins','Losses','Win %','Mean net %','Closed-trade compounded return %','Closed-trade drawdown %'],d.yearly.map(g=>[g.year,g.closed,g.wins,g.losses,fmt(g.win_rate_pct),fmt(g.mean_net_pct),fmt(g.closed_trade_return_pct),fmt(g.closed_trade_max_drawdown_pct)]));
table('branches',['Branch','Side','Evaluated','True','False','Unknown','Accepted primary','Same-side suppressed','Missing fields/reasons'],Object.entries(d.branch_diagnostics).map(([id,b])=>[id,b.side,b.evaluated,b.true,b.false,b.unknown,b.accepted,b.same_side_suppressed,JSON.stringify(b.missing_fields)]));
Object.keys(d.comparison?.groups||{}).forEach(key=>el('option','Revision: '+key,by('view')).value='comparison:'+key);
[...new Set(d.yearly.map(t=>t.year))].sort().forEach(v=>el('option',v,by('year')).value=v);
function render(){let records=d.trades,view=by('view').value;if(view==='wins')records=records.filter(t=>t.status==='CLOSED'&&t.net_pct>0);if(view==='failures')records=records.filter(t=>t.status==='CLOSED'&&t.net_pct<0);if(view==='unresolved')records=records.filter(t=>t.status!=='CLOSED');if(view.startsWith('comparison:'))records=(d.comparison.groups[view.slice(11)]||[]).map(t=>t.baseline?{...t.baseline,comparison:t}:t);records=records.filter(t=>by('year').value==='ALL'||new Date(t.buy_signal_time).getUTCFullYear().toString()===by('year').value);let shown=records.slice(page*50,page*50+50);table('trades',['BUY known UTC','SELL known UTC','BUY branch','SELL branch','Status','Net %','Inspect'],shown.map(t=>[stamp(t.buy_signal_time),stamp(t.sell_signal_time),t.buy_branch,t.sell_branch||'',t.status,fmt(t.net_pct),'']));by('trades').querySelectorAll('tr').forEach((tr,i)=>{if(i)el('button','Inspect',tr.lastChild).onclick=()=>by('detail').textContent=JSON.stringify({trade:shown[i-1],buy_signal:d.signals.find(s=>s.side==='BUY'&&s.known_time===shown[i-1].buy_signal_time),sell_signal:d.signals.find(s=>s.side==='SELL'&&s.known_time===shown[i-1].sell_signal_time)},null,2)});by('prev').disabled=page===0;by('next').disabled=(page+1)*50>=records.length;by('page').textContent=` ${records.length} records, page ${page+1}`;let signals=d.signals.slice(signalPage*50,signalPage*50+50);table('signals',['Known UTC','Side','Primary branch','All matched branches','Fill status','Fill UTC','Fill price'],signals.map(s=>[stamp(s.known_time),s.side,s.branch_id,s.matched_branches.join(', '),s.fill_status,stamp(s.fill_time),fmt(s.fill_price)]));by('signal-prev').disabled=signalPage===0;by('signal-next').disabled=(signalPage+1)*50>=d.signals.length;by('signal-count').textContent=`${d.signals.length} accepted signals. Signal page ${signalPage+1}; full chronological list is in JSON and details below.`;}
by('view').onchange=by('year').onchange=()=>{page=0;by('detail').textContent='';render()};by('prev').onclick=()=>{page--;render()};by('next').onclick=()=>{page++;render()};by('signal-prev').onclick=()=>{signalPage--;render()};by('signal-next').onclick=()=>{signalPage++;render()};by('config').textContent=JSON.stringify({config:d.config,contract:d.contract,definitions:d.definitions,comparison:d.comparison,signals:d.signals},null,2);render();</script></html>'''.replace('__REPORT__', data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--input', type=Path, help='Existing row source; defaults to BTC_1h_sequences/source_v1.json.gz')
    inputs.add_argument('--report', type=Path, help='Read-only fresh export from market memory using the existing frozen pivot-cohort report')
    parser.add_argument('--config', type=Path, required=True)
    baseline = parser.add_mutually_exclusive_group()
    baseline.add_argument('--baseline-config', type=Path, help='Replay this baseline on the exact same memory/window/costs')
    baseline.add_argument('--baseline', type=Path, help='Previously saved analyzer report with identical input contract')
    parser.add_argument('--since', type=timestamp, help='Inclusive candle knowledge-time boundary with timezone')
    parser.add_argument('--until', type=timestamp, help='Exclusive candle knowledge-time boundary with timezone')
    parser.add_argument('--output-dir', type=Path, default=Path('research_reports/BTC_1h_sequences/strategy_analyzer'))
    args = parser.parse_args()
    try:
        config = analyzer.validate_config(read(args.config))
        baseline_config = analyzer.validate_config(read(args.baseline_config)) if args.baseline_config else None
        if args.report:
            source = btc_hour_sequence_source.export(read(args.report), include_all_features=True,
                                                     progress=lambda r: print(r, flush=True))
            save(args.output_dir / 'memory_source.json.gz', source)
        else:
            source = read(args.input or Path('research_reports/BTC_1h_sequences/source_v1.json.gz'))
        report = analyzer.analyze(source, config, since=args.since, until=args.until)
        if baseline_config:
            original = analyzer.analyze(source, baseline_config, since=args.since, until=args.until)
        else:
            original = read(args.baseline) if args.baseline else None
        if original:
            report['comparison'] = analyzer.compare(original, report)
        save(args.output_dir / 'strategy_analysis.json.gz', report)
        page = args.output_dir / 'strategy_analysis.html'
        page.write_text(visual(report), encoding='utf-8')
        print(json.dumps(dict(strategy=config['id'], summary=report['summary'],
                              accepted_signals=len(report['signals']),
                              comparison=report.get('comparison', {}).get('counts')), indent=2))
        print('Report:', args.output_dir / 'strategy_analysis.json.gz')
        print('Dashboard:', page)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
