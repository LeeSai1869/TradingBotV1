"""Bounded, read-only pivot evidence export. No app imports or schema changes."""
import argparse
from contextlib import closing
from datetime import datetime,timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time

CODE_FILES=('Section_11_UI_UX/overlays/structure_tags/index.js',
 'Section_11_UI_UX/controls/settings/feature_styles.js',
 'Section_4_Features/features/market_structure.py',
 'Section_4_Features/features/structure_events.py',
 'Section_4_Features/execution/contract.py',
 'Section_4_Features/execution/components.py')


def quoted(value):return '"'+value.replace('"','""')+'"'


def columns(conn,schema,table):
    return [r[1] for r in conn.execute(f'PRAGMA {schema}.table_xinfo({quoted(table)})')]


def checkpoint_excerpt(text):
    data=json.loads(text);state=data.get('state',{});persistent=state.get('persistent',{})
    return {**{k:v for k,v in data.items() if k!='state'},'state':{
        **{k:state.get(k) for k in ('index','last_time','last_client')},
        'persistent':{k:v for k,v in persistent.items() if re.search('pivot|swing|structure|bos|choch|transition',k,re.I)}}}


def collect(project,symbol,interval,limit=6000,*,data_dir=None):
    project=Path(project).resolve()
    storage=Path(data_dir).expanduser().resolve()/'storage' if data_dir else project/'Section_1_Global_Core/memory_storage/Storage'
    features=storage/'features.db';raw=storage/'klines.db'
    for path in (features,raw):
        if not path.is_file():raise ValueError('Database not found: '+str(path))
    started=time.monotonic();now=int(time.time()*1000)
    with closing(sqlite3.connect(features.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)) as conn:
        conn.row_factory=sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        conn.set_progress_handler(lambda: int(time.monotonic()-started>20),10000)
        conn.execute('ATTACH DATABASE ? AS raw',(raw.resolve().as_uri()+'?mode=ro',))
        conn.execute('BEGIN')
        candles=[dict(r) for r in conn.execute('SELECT symbol,interval,open_time,close_time,open,high,low,close,volume FROM raw.klines '
            'WHERE symbol=? AND interval=? AND close_time<? ORDER BY open_time DESC LIMIT ?',(symbol,interval,now,limit))][::-1]
        if not candles:raise ValueError('No closed candles for '+symbol+' '+interval)
        fields=[c for c in columns(conn,'main','features') if re.search('pivot|swing|structure|protected|bos|choch|transition',c,re.I)
                or c in ('symbol','interval','open_time','formula_version','measurement_version','measurement_config_id','measurement_gap','atr')]
        if 'open_time' not in fields:raise ValueError('Feature schema has no open_time')
        projection=','.join(quoted(c) for c in fields)
        values={r['open_time']:dict(r) for r in conn.execute(f'SELECT {projection} FROM features WHERE symbol=? AND interval=? AND open_time>=? AND open_time<=? ORDER BY open_time',
            (symbol,interval,candles[0]['open_time'],candles[-1]['open_time']))}
        for candle in candles:candle['features']=values.get(candle['open_time'])
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        metadata={}
        for table in ('feature_engine_state','feature_calculation_versions','feature_replay_jobs'):
            if table not in tables:continue
            items=[dict(r) for r in conn.execute(f'SELECT * FROM {quoted(table)} WHERE symbol=? AND interval=?',(symbol,interval))]
            for item in items:
                if item.get('state'):
                    try:item['state']=checkpoint_excerpt(item['state'])
                    except (ValueError,TypeError):item['state']='Unrecognized checkpoint encoding'
            metadata[table]=items
    # All read transactions are closed before code capture/compression.
    code={}
    for relative in CODE_FILES:
        path=project/relative
        if path.is_file():
            content=path.read_text();code[relative]=dict(sha256=hashlib.sha256(content.encode()).hexdigest(),content=content)
    def git(*args):
        result=subprocess.run(['git','-C',str(project),*args],capture_output=True,text=True,timeout=10)
        return result.stdout.strip() if result.returncode==0 else None
    event_counts={'missing':0,'empty':0,'nonempty':0,'invalid':0}
    for candle in candles:
        event=(candle['features'] or {}).get('structure_events')
        if event is None:event_counts['missing']+=1
        else:
            try:event_counts['nonempty' if json.loads(event) else 'empty']+=1
            except (ValueError,TypeError):event_counts['invalid']+=1
    return dict(version=1,exported_utc=datetime.now(timezone.utc).isoformat(),symbol=symbol,interval=interval,
        project=str(project),paths={'features':str(features),'raw':str(raw)},git_head=git('rev-parse','HEAD'),
        code_status=git('status','--short','--',*CODE_FILES),fields=fields,metadata=metadata,code=code,candles=candles,
        summary=dict(candles=len(candles),feature_rows=len(values),first_open_ms=candles[0]['open_time'],
                     last_open_ms=candles[-1]['open_time'],event_rows=event_counts),
        consistency='Bounded read-only SQLite snapshots; raw and features may have separate writer checkpoints. No writes or recalculation.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--symbol',default='ENAUSDT');parser.add_argument('--interval',default='15m')
    parser.add_argument('--limit',type=int,default=6000);parser.add_argument('--data-dir',default=os.environ.get('TRADINGBOT_DATA_DIR'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.limit<=20000:parser.error('Limit must be 1..20000')
    if args.output.exists():parser.error('Output already exists; use a new filename')
    try:
        result=collect(args.project,args.symbol,args.interval,args.limit,data_dir=args.data_dir)
        with args.output.open('xb') as stream:
            with gzip.GzipFile(fileobj=stream,mode='wb') as compressed:compressed.write(json.dumps(result,allow_nan=False,separators=(',',':')).encode())
    except (ValueError,OSError,sqlite3.Error,subprocess.SubprocessError) as error:parser.exit(1,str(error)+'\n')
    print(json.dumps(result['summary'],indent=2));print('Attach this file: '+str(args.output.resolve()))
    print('Read-only export complete. No database values, settings, services or app code changed.')


if __name__=='__main__':main()
