"""Priority stages for the configured runner. No indicator or trading formulas.

Existing means a coin with a committed feature checkpoint on first deployment,
then the persisted cohort. Newly enabled coins join after full source/feature
catch-up. Paused intervals never participate in readiness barriers.
"""
from contextlib import closing
import importlib
import sqlite3
import time
from . import data_policy, work_priority
from .memory_storage.Storage import features_store, klines_store
from .memory_storage.market_data import update_klines

FEATURES='Section_4_Features.processor'
ANALYTICS='Section_1_Global_Core.analytical_processor'
DECISIONS='Section_8_Decision_Engine.processor'


def checkpoint_symbols():
    if not features_store.DB_PATH.exists():return set()
    with closing(sqlite3.connect(features_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='feature_engine_state'").fetchone():return set()
        return {r[0] for r in db.execute('SELECT DISTINCT symbol FROM feature_engine_state WHERE last_open_time IS NOT NULL')}


def pending_sources(symbols, intervals):
    """Only indexed endpoints/checkpoints; never scan historical candle payloads."""
    pending=[]
    if not symbols or not intervals:return pending
    if not klines_store.DB_PATH.exists():return [(s,t) for s in symbols for t in intervals]
    checkpoints={};versions={};repairs=set()
    if features_store.DB_PATH.exists():
        with closing(sqlite3.connect(features_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True)) as features:
            tables={r[0] for r in features.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'feature_engine_state' in tables:
                checkpoints={(s,t):v for s,t,v in features.execute('SELECT symbol,interval,last_open_time FROM feature_engine_state')}
            if 'feature_calculation_versions' in tables:
                versions={(s,t):v for s,t,v in features.execute('SELECT symbol,interval,signature FROM feature_calculation_versions')}
            if 'feature_replay_jobs' in tables:repairs=set(features.execute('SELECT symbol,interval FROM feature_replay_jobs'))
    components=importlib.import_module('Section_4_Features.execution.components')
    signature=components.current_signature();now=int(time.time()*1000)
    with closing(sqlite3.connect(klines_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True)) as raw:
        tables={r[0] for r in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'klines' not in tables:return [(s,t) for s in symbols for t in intervals]
        histories=set(raw.execute('SELECT symbol,interval FROM history_progress')) if 'history_progress' in tables else set()
        waits=klines_store.first_close_waits(raw,now)
        for s in symbols:
            for t in intervals:
                if (s,t) in waits:continue
                pair=(s,t)
                latest=raw.execute('SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=?',pair).fetchone()[0]
                checkpoint=checkpoints.get(pair)
                if (latest is None or pair in histories or now-latest>2*work_priority.interval_milliseconds(t)
                    or checkpoint is None or checkpoint<latest or pair in repairs or versions.get(pair)!=signature):
                    pending.append(pair)
    return pending


class PipelineScheduler:
    @classmethod
    def create(cls, processors, state):
        modules={name.rsplit('.',1)[0] for name,_ in processors}
        if not {FEATURES,ANALYTICS,DECISIONS}<=modules:return None
        return cls(state)

    def __init__(self,state):
        self.state=state
        self.modules={name:importlib.import_module(name) for name in (FEATURES,ANALYTICS,DECISIONS)}
        self.existing=[];self.new=[];self.events_allowed=False
        self.stage=None
        self.frontiers={}

    def cohorts(self):
        active=data_policy.active_symbols()
        cohort=self.state.get('__pipeline_existing__')
        if cohort is None:
            stored=checkpoint_symbols()
            cohort=[s for s in active if s in stored]
        # Persist removed coins too: re-enabling an existing coin does not make it new.
        self.state['__pipeline_existing__']=list(cohort)
        self.existing=[s for s in active if s in cohort]
        self.new=[s for s in active if s not in cohort]
        return self.existing,self.new

    def download(self):
        existing,new=self.cohorts()
        # Cold bootstrap gets one coin, not the entire new-listing universe.
        return update_klines.update_all(symbols=existing or new[:1])

    def announce(self,stage,pending=0,examples=()):
        message=(stage,pending,len(self.existing),len(self.new),tuple(examples))
        if message!=self.stage:
            print(f'[pipeline] stage={stage}; upstream_pending_pairs={pending}; existing={len(self.existing)}; initializing={len(self.new)}',flush=True)
            if examples:print(f'[pipeline] pending examples: {list(examples)}',flush=True)
            self.stage=message

    def maintain(self):
        self.cohorts();intervals=data_policy.active_intervals();rows={}
        self.events_allowed=False
        existing=self.existing
        if not existing:
            self.initialize(intervals,rows)
            return rows
        # Finish only pending source/formula/targeted repairs. _advance preserves
        # complete rows and resumes persisted checkpoints; no reset is requested.
        pending=pending_sources(existing,intervals)
        rows[FEATURES]=self.modules[FEATURES].maintenance(existing,intervals,max_bars=100000,time_budget=3 if pending else .3)
        pending=pending_sources(existing,intervals)
        if pending:
            self.announce('downloads/features',len(pending),pending[:5]);return rows
        self.announce('section5')
        analytics=self.modules[ANALYTICS]
        self.invalidate_frontiers(existing,intervals,analytics)
        rows[ANALYTICS]=analytics.maintenance(existing,intervals,max_bars=10000,time_budget=.5,max_pairs=1000,
            history_time_budget=3,history_max_bars=100000,history_max_pairs=10000,skip_complete=True)
        # Every engine must have reached the committed prefix. Dependency waits,
        # contention and errors are not completion, even if a turn produced zero.
        scopes=[(s,t,e) for s in existing for t in intervals
            if self.frontiers.get((s,t),(True,))[0] is not None
            for e in analytics.analytical_history.ENGINES]
        done={'caught up to committed feature prefix','caught up to common committed dependency prefix'}
        complete=all(analytics.analytical_history._messages.get(key) in done and analytics._status.get(key) in done for key in scopes)
        if not complete:
            waiting=sum(analytics.analytical_history._messages.get(key) not in done or analytics._status.get(key) not in done for key in scopes)
            print(f'[pipeline] section5 unfinished_scopes={waiting}/{len(scopes)}; classifications_this_turn={rows[ANALYTICS]}',flush=True)
            return rows
        self.events_allowed=True
        self.announce('buy/sell')
        rows[DECISIONS]=self.modules[DECISIONS].maintenance(existing,intervals,max_bars=100000,time_budget=1)
        if rows[DECISIONS]==0:self.initialize(intervals,rows)
        return rows

    def invalidate_frontiers(self,symbols,intervals,analytics):
        # A prior "caught up" belongs to a specific source prefix and producer.
        # Never release the decision barrier using yesterday's completion flags.
        from . import aggregation_processor
        generations=tuple(aggregation_processor.generation(e) for e in analytics.analytical_history.ENGINES)
        epoch=data_policy.read()['epochs']
        with closing(sqlite3.connect(features_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True)) as features:
            versions={(s,t):(sig,generation) for s,t,sig,generation in features.execute('SELECT symbol,interval,signature,generation FROM feature_calculation_versions')}
        with closing(sqlite3.connect(klines_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            for s in symbols:
                for t in intervals:
                    latest=db.execute('SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=?',(s,t)).fetchone()[0]
                    target=(latest,generations,versions.get((s,t)),epoch.get('symbol:'+s,0),epoch.get('interval:'+t,0))
                    if self.frontiers.get((s,t))!=target:
                        for e in analytics.analytical_history.ENGINES:
                            analytics._status.pop((s,t,e),None)
                            analytics.analytical_history._messages.pop((s,t,e),None)
                        self.frontiers[s,t]=target

    def initialize(self,intervals,rows):
        if not self.new or not intervals:return
        symbol=self.new[0]
        self.announce('new-coin initialization')
        rows['new_downloads']=update_klines.update_all(symbols=[symbol],time_budget=.5)
        rows[FEATURES]=rows.get(FEATURES,0)+self.modules[FEATURES].maintenance([symbol],intervals,max_bars=10000,time_budget=.5)
        if not pending_sources([symbol],intervals):
            self.state['__pipeline_existing__'].append(symbol)
            print(f'[pipeline] {symbol}: full candle/feature history ready; promoted to existing cohort',flush=True)

    def allow_event(self,name,symbol):
        # Event-driven downstream catch-up must respect the same global barrier.
        # Existing feature workers still own their normal bounded per-bar turns.
        if symbol not in self.existing:return False
        return name.rsplit('.',1)[0]!=DECISIONS or self.events_allowed
