"""Compare pivot outcomes by regime/trend and inspect Confidence/Opportunity evidence."""
import argparse
import gzip
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from contextlib import ExitStack
from Section_1_Global_Core import pivot_context_audit as audit,pivot_research,regime_inputs,intelligence_audit,data_policy
from Section_1_Global_Core.memory_storage.Storage import engine_store
from study_pivot_moves import push_report


def dashboard(packet):
    """Portable offline report; no scripts, market requests or CDN dependencies."""
    import html
    esc=lambda x:html.escape(str(x))
    lines=['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Pivot context audit</title>',
           '<style>body{font:16px system-ui;max-width:1200px;margin:25px auto;padding:15px;background:#111827;color:#e5e7eb}table{border-collapse:collapse;width:100%;margin:20px 0}td,th{text-align:left;padding:8px;border-bottom:1px solid #374151}meter{width:140px}details{margin:15px 0}small{color:#cbd5e1}a{color:#93c5fd}</style>',
           '<h1>'+esc(packet['symbol'])+' '+esc(packet['timeframe'])+' — pivot context audit</h1>',
           '<p>'+esc(packet['cohort'])+' · '+str(len(packet['cases']))+' of '+str(packet['source_pivots'])+' source pivots</p>',
           '<p>'+esc(packet['interpretation'])+'</p><h2>Engine history coverage</h2><pre>'+esc(json.dumps(packet['engine_history_status'],indent=2))+'</pre>']
    groups=packet['summary']['groups'];threshold=esc(packet.get('threshold_pct',2.))
    for dimension in ('confidence','confidence_mode','legacy_regime','local_regime','local_trend','4h_regime','4h_trend','1d_regime','1d_trend','alignment','regime_trend_htf','di_events','di_events_by_regime','confidence_by_regime'):
        lines.append('<details'+(' open' if dimension in ('confidence','local_regime','alignment') else '')+'><summary>'+esc(dimension)+'</summary><table><tr><th>Side / group</th><th>All cases</th><th>Resolved</th><th>'+threshold+'% after recognition</th></tr>')
        for row in groups:
            if row['year']!='ALL' or row['dimension']!=dimension:continue
            rate=row['hit_rate_pct'];bar='unavailable' if rate is None else f'<meter min="0" max="100" value="{rate}"></meter> {rate:.1f}%'
            lines.append('<tr><td>'+esc(row['side']+' / '+row['label'])+'</td><td>'+str(row['n'])+'</td><td>'+str(row['resolved'])+'</td><td>'+bar+'</td></tr>')
        lines.append('</table></details>')
    if packet.get('evidence_coverage'):lines.append('<h2>Saved decision coverage</h2><pre>'+esc(json.dumps(packet['evidence_coverage'],indent=2))+'</pre>')
    lines.append('<h2>Frozen Opportunity areas</h2><p>Touch means the subsequent candle range overlapped the area. It does not mean price reversed, or an order filled. Missing areas are not failures.</p><table><tr><th>Pivot side</th><th>Area / layer</th><th>Type</th><th>Observed</th><th>Resolved</th><th>Touch rate</th></tr>')
    for row in packet['summary']['opportunity_areas']:
        rate=row['touch_rate_pct'];lines.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in (row['side'],row['direction']+' '+str(row['layer']),'modeled' if row['modeled'] else 'native',row['n'],row['resolved'],'unavailable' if rate is None else f'{rate:.1f}%'))+'</tr>')
    lines.append('</table><h2>Case examples</h2><p>The compressed JSON contains every audited case. Below are the first 40 for visual review; times are UTC.</p>')
    from datetime import datetime,timezone
    for row in packet['cases'][:40]:
        stamp=datetime.fromtimestamp(row['known_time']/1000,timezone.utc).isoformat()
        lines.append('<details><summary>'+esc(stamp+' '+row['side']+' — '+row['after_known']['status'])+'</summary><pre style="white-space:pre-wrap">'+esc(json.dumps(row,indent=2))+'</pre></details>')
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--embedded-only',action='store_true',help='Audit the selected embedded examples without opening any market database')
    p.add_argument('--refresh-context-from',type=Path,help='Refresh only Regime/Trend joins in an existing audit, preserving scores/bands/outcomes')
    p.add_argument('--saved-decisions',action='store_true',help='Audit actual immutable BUY/SELL confidence and opportunity snapshots instead of pivot points')
    p.add_argument('--max-cases',type=int,help='Optional bounded prefix; omitted means all source cases')
    p.add_argument('--push-report',action='store_true');args=p.parse_args()
    if args.max_cases is not None and args.max_cases<1:p.error('--max-cases must be positive')
    if args.refresh_context_from and (args.saved_decisions or args.embedded_only):p.error('--refresh-context-from uses local histories and preserves its input cohort')
    if args.saved_decisions and args.embedded_only:p.error('--saved-decisions requires local market/ADCN databases')
    try:
        import os
        if hasattr(os,'nice'):os.nice(10)
        payload=args.report.read_bytes();report=json.loads(gzip.decompress(payload) if args.report.suffix=='.gz' else payload)
        audit.validate_report(report)
        with ExitStack() as stack:
            if args.embedded_only:reader=audit.EmbeddedReader(report)
            else:
                stack.enter_context(data_policy.snapshot_guard(timeout=1))
                source=regime_inputs.open_sources();stack.callback(source.close)
                metadata,cap=pivot_research.metadata(source,report['symbol'],report['timeframe'])
                if engine_store.digest(metadata)!=report['source_id']:raise ValueError('Feature generation/config differs from the source report; regenerate the pivot study before auditing')
                if cap<report['coverage']['last']:raise ValueError('Committed feature prefix does not cover the source report')
                engines=stack.enter_context(intelligence_audit.reader());reader=audit.LocalReader(source,engines,report)
            progress=lambda n,total:print(f'Audited {n}/{total}',flush=True)
            if args.refresh_context_from:
                prior=args.refresh_context_from.read_bytes();prior=json.loads(gzip.decompress(prior) if args.refresh_context_from.suffix=='.gz' else prior)
                packet=audit.refresh_context(prior,report,reader,progress=progress)
            elif args.saved_decisions:
                from Section_1_Global_Core.memory_storage.Storage import adcn_store
                snapshots=None
                if adcn_store.DB_PATH.is_file():
                    snapshots=sqlite3.connect(adcn_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=2);stack.callback(snapshots.close);snapshots.execute('BEGIN')
                packet=audit.audit_saved_decisions(report,reader,snapshots,max_cases=args.max_cases,progress=progress)
            else:packet=audit.audit(report,reader,embedded_only=args.embedded_only,max_cases=args.max_cases,progress=progress)
        # Serialize completely before publishing either artifact.
        payload=(json.dumps(packet,separators=(',',':'),allow_nan=False)+'\n').encode();page=dashboard(packet)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        if args.output.suffix=='.gz':payload=gzip.compress(payload,mtime=0)
        temp=args.output.with_name(args.output.name+'.partial');temp.write_bytes(payload);temp.replace(args.output)
        page_path=args.output.with_suffix('.html') if args.output.suffix!='.gz' else args.output.with_suffix('').with_suffix('.html')
        page_path.write_text(page,encoding='utf-8')
        print(json.dumps(dict(cohort=packet['cohort'],cases=len(packet['cases']),coverage=packet['summary']['coverage'],engine_history_status=packet['engine_history_status']),indent=2))
        print('Saved:',args.output,'and',page_path)
        if args.push_report:
            push_report(args.output);push_report(page_path)
    except (ValueError,OSError,RuntimeError,sqlite3.Error,subprocess.CalledProcessError) as error:p.exit(1,str(error)+'\n')

if __name__=='__main__':main()
