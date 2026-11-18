"""Read-only parity audit of ten EMA distance outputs; no storage retirement."""
import argparse
from collections import Counter
from contextlib import closing
import json
import math
import sqlite3
import time

from Section_1_Global_Core.memory_storage.Storage import features_store as store
from Section_4_Features.execution.ema_distances import FIELDS,INPUTS,values

KEYS=('rowid','symbol','interval','open_time','formula_version')
COLUMNS=(*KEYS,*INPUTS,*FIELDS)


def display(value):
    return repr(value) if isinstance(value,float) and not math.isfinite(value) else value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full',action='store_true',help='Check all version-3 rows through the captured maximum rowid')
    parser.add_argument('--sample',type=int,default=1000,help='SQL/Python sample size')
    parser.add_argument('--batch-size',type=int,default=5000)
    args=parser.parse_args()
    if not 1<=args.sample<=10000 or not 1<=args.batch_size<=10000:
        parser.error('Sample and batch size must be between 1 and 10000')
    checked=stored_bad=sql_bad=omitted=0
    counts=Counter();examples=[]
    def compare(row,*,sql=False):
        nonlocal checked,stored_bad,sql_bad,omitted
        expected=values(dict(zip(COLUMNS,row[:len(COLUMNS)])))
        for index,field in enumerate(FIELDS):
            original=row[len(KEYS)+len(INPUTS)+index]
            if original is None and expected[field] is not None:omitted+=1
            if original is not None and original!=expected[field]:
                stored_bad+=1;counts[field]+=1
                if len(examples)<5:
                    examples.append(dict(rowid=row[0],symbol=row[1],interval=row[2],
                        open_time=row[3],field=field,stored=display(original),derived=display(expected[field])))
            if sql and row[len(COLUMNS)+index]!=expected[field]:sql_bad+=1
        checked+=1

    with closing(sqlite3.connect(store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)) as conn:
        conn.execute('PRAGMA query_only=ON')
        target=conn.execute('SELECT max(rowid) FROM features').fetchone()[0] or 0
        projection=','.join('f.'+field for field in COLUMNS)
        sample=conn.execute('SELECT '+projection+','+
            ','.join(store.read_expression(field,preserve_legacy=False) for field in FIELDS)+
            ' FROM features f WHERE formula_version=3 AND rowid<=? '
            'ORDER BY rowid DESC LIMIT ?',(target,args.sample)).fetchall()
        for row in sample:compare(row,sql=True)
        sample_stored_bad=stored_bad
        if args.full:
            # SQL parity is sampled; full historical value parity uses the
            # independent Python provider, avoiding millions of scalar sorts.
            checked=stored_bad=omitted=0;counts.clear();examples.clear()
            last=0;printed=time.monotonic()
            print('Full EMA-distance audit; target rowid:',target,flush=True)
            while True:
                rows=conn.execute('SELECT '+projection+' FROM features f '
                    'WHERE formula_version=3 AND rowid>? AND rowid<=? '
                    'ORDER BY rowid LIMIT ?',(last,target,args.batch_size)).fetchall()
                if not rows:break
                for row in rows:compare(row)
                last=rows[-1][0]
                if time.monotonic()-printed>=15:
                    print(dict(rows_checked=checked,stored_formula_mismatches=stored_bad),flush=True)
                    printed=time.monotonic()
    report=dict(mode='full' if args.full else 'sample',target_rowid=target,
        rows_checked=checked,sql_sample_rows=len(sample),stored_formula_mismatches=stored_bad,
        omitted_values_reconstructed=omitted,
        sql_sample_stored_mismatches=sample_stored_bad,sql_python_mismatches=sql_bad,
        mismatches_by_field=dict(counts),examples=examples)
    print('FINAL:',json.dumps(report,allow_nan=False),flush=True)
    print('No database values or settings changed. Legacy versions were not retired. '
          'Concurrent replays may change rows during this pass.')
    if stored_bad or sample_stored_bad or sql_bad:raise SystemExit(1)


if __name__=='__main__':main()
