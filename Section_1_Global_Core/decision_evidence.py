"""Core-owned persistence bridge; calculators remain independent and read-only.

ADCN retains outputs once per decision, including historical reconstruction
provenance. Neither an HTTP read nor a chart refresh writes memory.
"""
import json
import time
from . import data_policy
from .memory_storage.Storage import adcn_store,features_store

_RECOVERY_CURSOR={}


def epoch_key(symbol,interval):
    epochs=data_policy.read()['epochs']
    from Section_10_Opportunity_Engine.engine import VERSION as opportunity_version
    return json.dumps([epochs.get(f'symbol:{symbol}',0),epochs.get(f'interval:{interval}',0),features_store.decision_generation(symbol,interval),opportunity_version],separators=(',',':'))


def capture(symbol,interval,open_times,*,provenance='closed decision worker',deadline=None):
    from .memory_storage.Storage import db
    count=0;epoch=epoch_key(symbol,interval)
    for opened in open_times:
        if deadline is not None and time.monotonic()>=deadline:break
        page=db.read_state_page(symbol,interval,1,before=opened+1)
        if not page['bars']:continue
        bar=page['bars'][-1];context=bar.get('signal_context')
        if bar['open_time']!=opened or not context or context['open_time']!=opened:continue
        if context['opportunity'].get('status')!='ready':continue
        with data_policy.locked():
            if epoch_key(symbol,interval)!=epoch:return count
            conn=adcn_store.open_db()
            try:
                row=adcn_store.read_row(conn,symbol,interval,opened)
                if row and row['signal_type']==context['side']:
                    count+=adcn_store.save_evidence(conn,symbol,interval,epoch,context,recorded_ms=int(time.time()*1000),provenance=provenance)
            finally:conn.close()
    if count:print(f'[evidence] {symbol} {interval}: +{count} immutable decision snapshots; {provenance}',flush=True)
    return count


def recover_one(symbol,interval,*,deadline=None):
    if not adcn_store.DB_PATH.exists():return 0
    conn=adcn_store.open_db()
    key=(str(adcn_store.DB_PATH),symbol,interval,epoch_key(symbol,interval))
    try:rows=adcn_store.missing_evidence(conn,symbol,interval,key[-1],after=_RECOVERY_CURSOR.get(key,-1))
    finally:conn.close()
    _RECOVERY_CURSOR[key]=rows[-1][0] if rows else -1
    count=capture(symbol,interval,[r[0] for r in rows],provenance='historical reconstruction from stored close-time inputs',deadline=deadline)
    if not count and (deadline is None or time.monotonic()<deadline):count+=recover_history_page(symbol,interval,deadline=deadline)
    return count


def recover_history_page(symbol,interval,*,deadline=None):
    """Persist older chart-projected signals even when ADCN had no original row."""
    from .memory_storage.Storage import db
    epoch=epoch_key(symbol,interval);conn=adcn_store.open_db()
    try:state=adcn_store.evidence_scan_state(conn,symbol,interval,epoch)
    finally:conn.close()
    if state and state[1]:return 0
    before=state[0] if state else None
    page=db.read_state_page(symbol,interval,64,before=before,context_history=True)
    contexts=[b['signal_context'] for b in page['bars'] if b.get('signal_context') and b['signal_context']['open_time']==b['open_time']
              and b['signal_context']['opportunity'].get('status')=='ready']
    count=0
    with data_policy.locked():
        if epoch_key(symbol,interval)!=epoch:return 0
        conn=adcn_store.open_db()
        try:
            for context in contexts:
                if deadline is not None and time.monotonic()>=deadline:return count
                if adcn_store.ensure_historical_decision(conn,symbol,interval,context):
                    count+=adcn_store.save_evidence(conn,symbol,interval,epoch,context,recorded_ms=int(time.time()*1000),
                        provenance='historical reconstruction from stored close-time inputs')
            # Retry a page with missing features; never silently skip unknown history.
            ready=all((b.get('features') or {}).get('formula_version')==3 and ((b.get('momentum') or {}).get('signal_type') not in ('BUY','SELL') or (b.get('opportunity') or {}).get('status')=='ready') for b in page['bars'])
            if page['bars'] and ready:
                adcn_store.commit_evidence_scan(conn,symbol,interval,epoch,page['next_before'],page['next_before'] is None)
        finally:conn.close()
    if count:print(f'[evidence] {symbol} {interval}: +{count} historical decision snapshots',flush=True)
    return count
