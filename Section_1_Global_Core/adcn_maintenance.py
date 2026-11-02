"""Explicit ADCN-only maintenance; no candle/feature writes or automatic cleanup."""
import ast
from pathlib import Path
import hashlib
import json
from contextlib import closing
from . import data_policy
from .memory_storage.Storage import adcn_store

# Live rule, identity and availability fields are never eligible for retirement.
PROTECTED={'symbol','interval','open_time','trigger','signal_type','decision_state'}
ARCHIVED=set(adcn_store.COLUMNS)-PROTECTED
def protected_fields():
    """Conservative key dependencies in the current decision/evidence consumers.

    Generic compatibility readers can still return NULL for retired archive keys.
    A new explicit key dependency in these live consumers makes it ineligible.
    """
    root=Path(__file__).resolve().parent.parent
    files=[root/'Section_8_Decision_Engine'/name for name in ('processor.py','presentation.py','sequence.py')]
    files+=list((root/'Section_8_Decision_Engine'/'rules').glob('*.py'))
    files+=[root/'Section_1_Global_Core'/name for name in ('decision_evidence.py','analysis.py')]
    keys=set(PROTECTED)
    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value in adcn_store.COLUMNS:keys.add(node.value)
    return keys


CONFIRMATION='RETIRE ADCN DATA'


def catalog():
    with closing(adcn_store.open_db()) as conn:
        retired={r[0] for r in conn.execute('SELECT field FROM retired_fields')}
    protected=protected_fields()
    return {'confirmation':CONFIRMATION,'fields':[dict(field=f,protected=f in protected,retired=f in retired,
        reason='Required by identity, current Decision Engine, alerts and anchored evidence' if f in protected else
        'Archived interpretation/score storage; no producer in the current DI decision pipeline') for f in adcn_store.COLUMNS],
        'note':'Retiring clears archived values and suppresses future writes to that field. It preserves the compatibility column. Current decision evidence, checkpoints, candles and permanent features are protected. Cleared pages become reusable; the database file may not shrink.'}


def validate(data):
    fields=data.get('fields',[])
    if not isinstance(fields,list) or any(not isinstance(f,str) for f in fields) or len(fields)>len(ARCHIVED):raise ValueError('Select archived ADCN fields')
    fields=sorted(set(fields))
    if set(fields)-(set(adcn_store.COLUMNS)-protected_fields()):raise ValueError('Protected or unknown field: current dependencies prevent retirement')
    delete=data.get('delete_legacy',False)
    if type(delete) is not bool:raise ValueError('Choose whether to delete obsolete signal history')
    symbol=data.get('symbol') or None;interval=data.get('interval') or None
    if symbol is not None and (not isinstance(symbol,str) or not symbol.isalnum() or len(symbol)>30):raise ValueError('Invalid symbol')
    if interval is not None and interval not in data_policy.INTERVALS:raise ValueError('Invalid timeframe')
    if not fields and not delete:raise ValueError('Select fields or obsolete history to preview')
    return fields,delete,symbol,interval


def scope(symbol,interval):
    terms=[];values=[]
    for key,value in (('symbol',symbol),('interval',interval)):
        if value is not None:terms.append('d.'+key+'=?');values.append(value)
    return (' AND '.join(terms) or '1'),values


def preview_in(conn,data):
    fields,delete,symbol,interval=validate(data)
    where,args=scope(symbol,interval)
    # NULL-trigger WAIT/SUPPRESSED rows are current state, not obsolete signals.
    legacy=f"""{where} AND d.signal_type IN ('BUY','SELL') AND COALESCE(d.trigger,'')!='DI_TURNING_POINT_V3'
        AND NOT EXISTS(SELECT 1 FROM decision_evidence e WHERE e.symbol=d.symbol AND e.interval=d.interval AND e.open_time=d.open_time)
        AND NOT EXISTS(SELECT 1 FROM decision_rule_state r WHERE r.symbol=d.symbol AND r.interval=d.interval AND r.last_open_time=d.open_time)"""
    count=conn.execute('SELECT COUNT(*),COALESCE(MAX(rowid),0) FROM decisions d WHERE '+legacy,args).fetchone() if delete else (0,0)
    # Retirement is global: partial retirement would leave an ambiguous writer policy.
    counts=conn.execute('SELECT '+','.join(f'COUNT("{f}")' for f in fields)+' FROM decisions').fetchone() if fields else []
    affected=dict(zip(fields,counts))
    packet=dict(fields=fields,clear_values=affected,delete_legacy=delete,obsolete_rows=count[0],symbol=symbol,interval=interval)
    packet['token']=hashlib.sha256(json.dumps([packet,count[1]],sort_keys=True).encode()).hexdigest()
    return packet,legacy,args


def preview(data):
    with data_policy.snapshot_guard(),closing(adcn_store.open_db()) as conn:return preview_in(conn,data)[0]


def apply(data):
    if data.get('confirmation')!=CONFIRMATION:raise ValueError('Type '+CONFIRMATION+' to confirm permanent clearing')
    with data_policy.locked(),data_policy.snapshot_guard(exclusive=True),closing(adcn_store.open_db()) as conn:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            packet,legacy,args=preview_in(conn,data)
            if data.get('token')!=packet['token']:raise ValueError('Preview changed. Review a fresh preview before confirming.')
            for field in packet['fields']:
                conn.execute(f'UPDATE decisions SET "{field}"=NULL WHERE "{field}" IS NOT NULL')
                conn.execute('INSERT OR IGNORE INTO retired_fields(field) VALUES (?)',(field,))
            if packet['delete_legacy']:conn.execute('DELETE FROM decisions AS d WHERE '+legacy,args)
            return packet


def restore(field):
    if field not in ARCHIVED or field in protected_fields():raise ValueError('Only archived fields can be restored')
    with data_policy.locked(),closing(adcn_store.open_db()) as conn:
        with conn:conn.execute('DELETE FROM retired_fields WHERE field=?',(field,))
    return {'restored':field,'note':'Future storage allowed. Previously cleared values are not recovered or recalculated.'}
