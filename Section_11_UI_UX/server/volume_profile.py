"""Read the runner's existing histogram; never calculate or fetch market data here."""
import json
import math
import sqlite3
from collections import OrderedDict
from Section_1_Global_Core.memory_storage.Storage import features_store

_CACHE=OrderedDict()

def snapshot(symbol,interval,latest,epoch):
    def waiting(reason,**details):return {'status':'waiting for volume-profile checkpoint','reason':reason,'bins':[],**details}
    if not latest:return waiting('No closed candle is available')
    if not features_store.DB_PATH.exists():return waiting('Feature database is unavailable')
    conn=sqlite3.connect(features_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)
    try:
        conn.execute('BEGIN')
        row=conn.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
        if not row:return waiting('Feature checkpoint has not been created')
        if row[0]>latest['open_time']:return waiting('Histogram checkpoint is newer than the requested candle',checkpoint_time=row[0],requested_time=latest['open_time'])
        task=features_store.pending_replay(conn,symbol,interval)
        if task and any(c.startswith('vp_') for c in task[2]):return waiting('Volume Profile recalculation is pending')
        revision=None
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='feature_calculation_versions'").fetchone():
            revision=conn.execute('SELECT signature,generation FROM feature_calculation_versions WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
        stale=row[0]<latest['open_time']
        f=(features_store.read_row(conn,symbol,interval,row[0]) or {}) if stale else (latest.get('features') or {})
        levels={k:f.get(k) for k in ('vp_poc','vp_va_low','vp_va_high')}
        if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in levels.values()):return waiting('Stored POC or value-area levels are unavailable')
        key=(str(features_store.DB_PATH),symbol,interval,epoch,row[0],revision,tuple(levels.values()))
        freshness=dict(stale=stale,requested_time=latest['open_time'])
        if key in _CACHE:return {**_CACHE[key],**freshness}
        state=conn.execute('SELECT state FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
        saved=json.loads(state[0]);values=saved['state'];params=saved['parameters']
        if saved.get('version')!=3 or ':'.join(map(str,saved.get('epoch',())))!=epoch:return waiting('Histogram checkpoint version or data epoch differs')
        if values.get('last_time')!=row[0]:return waiting('Histogram state timestamp differs from its checkpoint')
        count=params['vpBins'];lookback=params['vpLookback'];volumes=values['persistent'].get('vpVolumeBins',[])
        high=values['histories'].get('h',[])[-lookback:];low=values['histories'].get('l',[])[-lookback:]
        finite=lambda v:isinstance(v,(float,int)) and math.isfinite(v)
        if len(high)<lookback or len(low)<lookback:return waiting('Not enough stored candles for the histogram lookback',required=lookback,highs=len(high),lows=len(low))
        if len(volumes)!=count or not all(finite(v) for v in high+low+volumes):return waiting('Histogram bins or price history contain invalid data')
        floor=min(low);ceiling=max(high);size=(ceiling-floor)/count;maximum=max(volumes)
        if size<=0 or maximum<=0:return waiting('Histogram price range or recorded volume is zero')
        poc=volumes.index(maximum)
        if not math.isclose(floor+(poc+.5)*size,levels['vp_poc'],rel_tol=1e-10,abs_tol=1e-10):return waiting('Stored histogram does not match its POC level')
        bins=[{'low':floor+i*size,'high':floor+(i+1)*size,'volume':v,
               'node':'high' if v>=maximum*.7 else 'low' if v<=maximum*.3 else 'normal'} for i,v in enumerate(volumes)]
        result={'status':'ready','as_of':row[0],'lookback':lookback,'value_area_pct':params['vpValueAreaPct'],'bins':bins,'levels':levels}
        _CACHE[key]=result
        while len(_CACHE)>16:_CACHE.popitem(last=False)
        return {**result,**freshness}
    except (KeyError,ValueError,TypeError,sqlite3.OperationalError) as error:return waiting('Histogram checkpoint could not be read',error_type=type(error).__name__)
    finally:conn.close()
