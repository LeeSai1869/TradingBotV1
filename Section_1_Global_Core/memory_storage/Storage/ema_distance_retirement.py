"""Verify and omit the ten version-3 same-candle EMA derivatives atomically."""
from collections import defaultdict
from Section_4_Features.execution.ema_distances import FIELDS,INPUTS,values

COLUMNS=('rowid','symbol','interval','open_time','formula_version',*INPUTS,*FIELDS)


def projection(prefix='f'):
    return ','.join(prefix+'.'+field for field in COLUMNS)


def clear_rows(conn, rows, *, apply):
    """Validate the entire batch before updating any cells; legacy stays stored."""
    if apply and not conn.in_transaction:
        raise RuntimeError('EMA-distance clearing requires a write transaction')
    report=dict(rows_checked=0,rows_cleared=0,values_cleared=0,values_retained=0)
    groups=defaultdict(list)
    for row in rows:
        item=dict(zip(COLUMNS,row))
        report['rows_checked']+=1
        populated=[field for field in FIELDS if item[field] is not None]
        if item['formula_version']!=3:
            report['values_retained']+=len(populated)
            continue
        if not populated:continue
        expected=values(item)
        for field in populated:
            if item[field]!=expected[field]:
                raise ValueError(f'EMA distance formula mismatch: {item["symbol"]} '
                    f'{item["interval"]} {item["open_time"]} {field}; batch unchanged')
        groups[tuple(populated)].append(item['rowid'])
        report['rows_cleared']+=1
        report['values_cleared']+=len(populated)
    if apply:
        for names,group in groups.items():
            for offset in range(0,len(group),900):
                ids=group[offset:offset+900];parameters=','.join('?' for _ in ids)
                conn.execute('UPDATE features SET '+','.join(field+'=NULL' for field in names)+
                    ' WHERE formula_version=3 AND rowid IN ('+parameters+')',ids)
                remaining=conn.execute('SELECT rowid FROM features WHERE rowid IN ('+parameters+
                    ') AND ('+' OR '.join(field+' IS NOT NULL' for field in names)+') LIMIT 1',ids).fetchone()
                if remaining:raise RuntimeError('EMA distance clear read-back failed')
    return report


def retire_written(conn, keys):
    """Reuse persisted inputs within the feature/checkpoint write transaction."""
    if not conn.in_transaction:
        raise RuntimeError('EMA-distance retirement requires a write transaction')
    pairs=defaultdict(set)
    for symbol,interval,stamp in keys:pairs[(symbol,interval)].add(stamp)
    rows=[]
    for (symbol,interval),times in pairs.items():
        stamps=sorted(times)
        for offset in range(0,len(stamps),800):
            chunk=stamps[offset:offset+800]
            found=conn.execute('SELECT '+projection()+' FROM features f '
                'WHERE symbol=? AND interval=? AND open_time IN ('+
                ','.join('?' for _ in chunk)+')',[symbol,interval,*chunk]).fetchall()
            if len(found)!=len(chunk):raise RuntimeError('Feature row disappeared during EMA distance verification')
            rows.extend(found)
    return clear_rows(conn,rows,apply=True)
