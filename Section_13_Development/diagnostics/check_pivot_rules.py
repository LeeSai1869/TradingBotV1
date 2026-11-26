"""Read-only status of the pivot-rule update and its pair-specific repair."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3


def status(project,symbol,interval):
    root=os.environ.get('TRADINGBOT_DATA_DIR')
    path=Path(root).expanduser()/'storage/features.db' if root else Path(project)/'Section_1_Global_Core/memory_storage/Storage/features.db'
    if not path.is_file():raise ValueError('Feature database not found: '+str(path))
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)) as conn:
        conn.row_factory=sqlite3.Row;conn.execute('BEGIN')
        fields={r[1] for r in conn.execute('PRAGMA table_xinfo(features)')}
        names=[k for k in ('open_time','pivot_rules_version','pivot_reference_range','pivot_confirmation_level','pivot_reverse_closes','candidate_pivot','protected_high','protected_low','current_structure','structure_range_high','structure_range_low') if k in fields]
        latest=conn.execute('SELECT '+','.join(names)+' FROM features WHERE symbol=? AND interval=? ORDER BY open_time DESC LIMIT 1',(symbol,interval)).fetchone()
        job=None
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='feature_replay_jobs'").fetchone():
            record=conn.execute('SELECT last_time,target,columns FROM feature_replay_jobs WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
            if record:job=dict(last_time=record[0],target=record[1],columns=json.loads(record[2]))
        return dict(symbol=symbol,interval=interval,latest=dict(latest) if latest else None,repair=job,
                    status='REPAIR_PENDING' if job else 'UPDATED' if latest and 'pivot_rules_version' in names and latest['pivot_rules_version']=='confirmed-pair-v1' else 'AWAITING_UPDATED_WRITER')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--symbol',default='ENAUSDT');p.add_argument('--interval',default='15m');p.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[2]);a=p.parse_args()
    print(json.dumps(status(a.project,a.symbol,a.interval),indent=2))


if __name__=='__main__':main()
