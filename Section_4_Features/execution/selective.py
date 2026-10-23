"""Resumable affected-column replay, preserving the normal chronological checkpoint."""
from collections import deque
import copy
import json
from . import checkpoint,runtime as rt,memory
from .components import catalog,desired_parameters,current_signature,digest
from .context import Context,MANIFEST
from .contract import ALIASES
from .engine import Engine


class PartialEngine:
    def __init__(self,symbol,interval,plan,parameters,context=None):
        self.context=context or Context(symbol,interval,parameters)
        self.plan=plan;self.component_sources=catalog().source
    def step(self,client,stored,*,daily_bars=None):
        e=self.context;e._stored=stored;e.begin(client,stored=stored,helpers=self.plan.execute);e.external_daily=daily_bars;memory.update(e)
        for field in self.plan.reads|self.plan.history_keys|{'regimeState'}:
            column=catalog().export.get(field)
            if column and field not in self.plan.state_writes:e.values[field]=rt.NA if stored.get(column) is None else stored[column]
        for fn in self.plan.functions:fn(e)
        inverse=catalog().export_inverse
        result={}
        for column in self.plan.columns:
            if column in ALIASES:column_source=ALIASES[column]
            else:column_source=column
            if column_source.startswith('prev_') and column_source[5:] in ('atr','ema7','ema25','ema50','ema100','ema200','ema300'):
                result[column]=e.previous(column_source[5:],1)
            elif column_source in inverse:result[column]=e[inverse[column_source]]
        for side,prefix in [('support','support'),('resistance','resistance'),('inst_support','instSupport'),('inst_resistance','instResistance')]:
            edges=[edge for edge in ('low','high') if f'{side}_zone_{edge}' in self.plan.columns]
            if not edges:continue
            ids=e.persistent.get(prefix+'ZoneIDArray',[]);identity=e.values.get('nearest'+prefix[0].upper()+prefix[1:]+'ZoneID')
            index=ids.index(identity) if identity in ids else None
            for edge in edges:
                levels=e.persistent.get(prefix+edge.title()+'Array',[])
                result[f'{side}_zone_{edge}']=levels[index] if index is not None and index<len(levels) else None
        result['open_time']=client['open_time']
        e.finish(history_keys=self.plan.history_keys);return rt.clean(result)



def merge(base,partial):
    merged=copy.deepcopy(base);a=merged.context;b=partial.context;plan=partial.plan
    a.parameters=dict(b.parameters);a.capacity=b.capacity
    for site in plan.sites:
        if site in b.technical:a.technical[site]=copy.deepcopy(b.technical[site])
        else:a.technical.pop(site,None)
    for key in plan.state_writes:
        if key in b.persistent:a.persistent[key]=copy.deepcopy(b.persistent[key])
    for key,values in b.histories.items():
        if key in plan.state_writes or key in catalog().export:a.histories[key]=deque(values,maxlen=a.capacity)
    if 'context:vwap' in plan.execute:a.vwap_sum=b.vwap_sum;a.vwap_volume=b.vwap_volume
    if 'context:volume' in plan.execute:a.volumes=list(b.volumes)
    if 'regimeState' in plan.state_writes:a.last_regime=b.last_regime
    merged.component_sources=catalog().source
    return merged


def read_job(conn,symbol,interval):
    row=conn.execute('SELECT signature,target,last_time,changed,state FROM feature_replay_jobs WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
    return dict(zip(('signature','target','last_time','changed','state'),row)) if row else None


def changed(engine):
    c=catalog();params=desired_parameters()
    if engine.component_sources==c.source and engine.context.parameters==params:return set()
    return c.changed(engine.component_sources or {},engine.context.parameters,params)


def prepare(conn,engine,epoch):
    """Call under the Core writer guard. Never invalidate unrelated components."""
    e=engine.context;job=read_job(conn,e.symbol,e.timeframe);signature=current_signature()
    # f67025e used ast.dump defaults, which changed in Python 3.13+. Recognize
    # that exact old fingerprint of the *current* formulas, never arbitrary old
    # formulas. Affected jobs changed identical formulas and can be retired while
    # genuine parameter changes below still receive a selective repair.
    if engine.component_sources!=catalog().source or job and job['signature']!=signature:
        from .components import legacy_runtime_sources
        legacy=legacy_runtime_sources()
        if engine.component_sources==legacy:engine.component_sources=catalog().source
        legacy_signature=digest([digest(legacy),desired_parameters()])
        if job and job['signature']==legacy_signature and engine.component_sources==catalog().source:
            conn.execute('DELETE FROM feature_replay_jobs WHERE symbol=? AND interval=?',(e.symbol,e.timeframe))
            print(f'[features] {e.symbol} {e.timeframe}: retired Python AST-format-only repair; main checkpoint preserved at {e.last_time}',flush=True)
            job=None
    dirty=changed(engine)
    if job and job['signature']==signature:return job
    if job:
        for uid in json.loads(job['changed']):
            if uid in catalog().by_id:dirty.add(uid)
            else:dirty.update(u.id for u in catalog().units if u.module==uid.split(':',1)[0])
    if not dirty or e.last_time is None:
        engine.component_sources=catalog().source
        if e.last_time is not None:
            conn.execute('UPDATE feature_engine_state SET state=? WHERE symbol=? AND interval=?',(checkpoint.dump(engine,epoch),e.symbol,e.timeframe))
            conn.execute('INSERT INTO feature_calculation_versions(symbol,interval,signature,generation) VALUES (?,?,?,0) ON CONFLICT(symbol,interval) DO UPDATE SET signature=excluded.signature',(e.symbol,e.timeframe,signature))
        return None
    plan=catalog().plan(dirty)
    columns=sorted(plan.columns)
    from Section_1_Global_Core.memory_storage.Storage import features_store
    critical=bool(set(columns)&set(features_store.decision_fields()+['c','close']))
    # Only DI/ADX/price changes invalidate the current strategy's inputs.
    conn.execute('INSERT INTO feature_calculation_versions(symbol,interval,signature,generation) VALUES (?,?,?,?) ON CONFLICT(symbol,interval) DO UPDATE SET generation=generation+?',(e.symbol,e.timeframe,'',int(critical),int(critical)))
    previous=conn.execute('SELECT invalidated_columns FROM feature_calculation_versions WHERE symbol=? AND interval=?',(e.symbol,e.timeframe)).fetchone()
    invalidated=set(json.loads(previous[0]) if previous else [])|set(columns)
    conn.execute('UPDATE feature_calculation_versions SET invalidated_columns=? WHERE symbol=? AND interval=?',(json.dumps(sorted(invalidated)),e.symbol,e.timeframe))
    conn.execute('INSERT OR REPLACE INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',
                 (e.symbol,e.timeframe,signature,e.last_time,-1,json.dumps(sorted(dirty)),None,json.dumps(columns)))
    print(f'[features] {e.symbol} {e.timeframe}: targeted replay scheduled; {len(dirty)} calculation units, columns={columns}',flush=True)
    return read_job(conn,e.symbol,e.timeframe)
