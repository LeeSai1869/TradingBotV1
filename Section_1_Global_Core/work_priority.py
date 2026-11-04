"""Closest-to-completion bulk priority with bounded service for other pairs."""
from contextlib import closing
import sqlite3
import time
from .memory_storage.Storage import klines_store,features_store

_selected=None
_identity=None


def work_symbol(symbols,intervals):
    """Keep the current symbol until its raw history and feature checkpoints finish.

    Existing symbols closest to completion precede larger backlogs and empty symbols. Never use feature
    row counts as replay progress: older formula rows can still exist.
    """
    global _selected,_identity
    symbols=list(symbols);intervals=set(intervals)
    identity=(str(klines_store.DB_PATH),str(features_store.DB_PATH),tuple(symbols),tuple(sorted(intervals)))
    if identity!=_identity:_selected=None;_identity=identity
    if not symbols or not intervals:return None
    if not klines_store.DB_PATH.exists():return symbols[0]
    with closing(sqlite3.connect(f'file:{klines_store.DB_PATH}?mode=ro',uri=True,timeout=2)) as raw:
        history=set(raw.execute('SELECT symbol,interval FROM history_progress')) if raw.execute("SELECT 1 FROM sqlite_master WHERE name='history_progress'").fetchone() else set()
        waiting=klines_store.first_close_waits(raw,int(time.time()*1000))
        history_cursors={}
        if history and 'next_open_time' in {r[1] for r in raw.execute('PRAGMA table_info(history_progress)')}:
            history_cursors={(s,t):v for s,t,v in raw.execute('SELECT symbol,interval,next_open_time FROM history_progress')}
        checkpoints={};versions=None;jobs=set();repairs={}
        if features_store.DB_PATH.exists():
            with closing(sqlite3.connect(f'file:{features_store.DB_PATH}?mode=ro',uri=True,timeout=2)) as features:
                if features.execute("SELECT 1 FROM sqlite_master WHERE name='feature_engine_state'").fetchone():
                    checkpoints={(s,t):v for s,t,v in features.execute('SELECT symbol,interval,last_open_time FROM feature_engine_state')}
                if features.execute("SELECT 1 FROM sqlite_master WHERE name='feature_calculation_versions'").fetchone():
                    from Section_4_Features.execution.components import current_signature
                    signature=current_signature()
                    versions={(s,t):v for s,t,v in features.execute('SELECT symbol,interval,signature FROM feature_calculation_versions')}
                    jobs=set(features.execute('SELECT symbol,interval FROM feature_replay_jobs'))
                    repairs={(s,t):(last,target) for s,t,last,target in features.execute('SELECT symbol,interval,last_time,target FROM feature_replay_jobs')}
        def pending(s):
            for t in intervals:
                if (s,t) in waiting:continue
                if (s,t) in history or (s,t) in jobs or versions is not None and versions.get((s,t))!=signature:return True
                # Indexed point lookup; never scan millions of candles per cycle.
                latest=raw.execute('SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=?',(s,t)).fetchone()[0]
                if latest is None or checkpoints.get((s,t),-1)<latest:return True
            return False
        if _selected in symbols and pending(_selected):return _selected
        def backlog(symbol):
            remaining=0.;populated=False
            for interval in intervals:
                if (symbol,interval) in waiting:continue
                first=raw.execute('SELECT MIN(open_time) FROM klines WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()[0]
                latest=raw.execute('SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()[0]
                if latest is None:remaining+=float('inf');continue
                populated=True
                step=interval_milliseconds(interval)
                through=checkpoints.get((symbol,interval),first-step)
                remaining+=max(0,latest-through)/step
                repair=repairs.get((symbol,interval))
                if repair:remaining+=max(0,repair[1]-max(first-step,repair[0]))/step
                elif versions is not None and versions.get((symbol,interval))!=signature:
                    remaining+=max(1,(through-first)/step)
                if (symbol,interval) in history:
                    cursor=history_cursors.get((symbol,interval))
                    remaining+=max(1,(latest-cursor)/step) if cursor is not None else 1
            return (not populated,remaining,symbols.index(symbol))
        candidates=[s for s in symbols if pending(s)]
        _selected=min(candidates,key=backlog) if candidates else None
    return _selected


def interval_milliseconds(interval):
    units={'m':60000,'h':3600000,'d':86400000,'w':604800000,'M':2678400000}
    return max(1,int(interval[:-1])*units[interval[-1]])


def owns_history(symbol):
    return _selected is None or _selected==symbol


_service_cursors={}
_live_cursors={}
_service_phases={}

def service_pair(symbols,intervals,owner,kind,*,owner_interval=None):
    """Give non-owner pairs bounded turns without changing bulk ownership.

    Only indexed existence checks are used. Every connection closes even when a
    candidate is returned early; garbage collection must never own this lifetime.
    """
    from contextlib import ExitStack
    if kind not in ('downloads','features'):raise ValueError('Unknown service kind')
    symbols=list(symbols);intervals=list(intervals)
    pairs=[(s,t) for s in symbols for t in reversed(intervals) if s!=owner or owner_interval is not None and t!=owner_interval]
    if not pairs or not klines_store.DB_PATH.exists():return None
    identity=(str(klines_store.DB_PATH),str(features_store.DB_PATH),tuple(pairs),kind)
    cursor=_service_cursors.get(identity,0)
    # Policies can change; retain no more than the current scheduler identities.
    if len(_service_cursors)>8:_service_cursors.clear()
    with ExitStack() as stack:
        raw=stack.enter_context(closing(sqlite3.connect(klines_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)))
        history={}
        waiting=klines_store.first_close_waits(raw,int(time.time()*1000))
        if raw.execute("SELECT 1 FROM sqlite_master WHERE name='history_progress'").fetchone():
            cols={r[1] for r in raw.execute('PRAGMA table_info(history_progress)')}
            history={(s,t):v for s,t,v in raw.execute('SELECT symbol,interval,next_open_time FROM history_progress')} if 'next_open_time' in cols else {tuple(r):None for r in raw.execute('SELECT symbol,interval FROM history_progress')}
        checkpoints={};jobs=set();versions=None
        if kind=='features' and features_store.DB_PATH.exists():
            features=stack.enter_context(closing(sqlite3.connect(features_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)))
            if features.execute("SELECT 1 FROM sqlite_master WHERE name='feature_engine_state'").fetchone():checkpoints={(s,t):v for s,t,v in features.execute('SELECT symbol,interval,last_open_time FROM feature_engine_state')}
            if features.execute("SELECT 1 FROM sqlite_master WHERE name='feature_replay_jobs'").fetchone():jobs=set(features.execute('SELECT symbol,interval FROM feature_replay_jobs'))
            if features.execute("SELECT 1 FROM sqlite_master WHERE name='feature_calculation_versions'").fetchone():
                from Section_4_Features.execution.components import current_signature
                signature=current_signature();versions={(s,t):v for s,t,v in features.execute('SELECT symbol,interval,signature FROM feature_calculation_versions')}
        # Alternate near-current work and historical background turns. A
        # universe full of targeted replays must not make a ready pair wait an
        # entire rotation just to calculate its next closed candle.
        phase=_service_phases.get(identity,0)
        if len(_service_phases)>8:_service_phases.clear();_live_cursors.clear()
        _service_phases[identity]=phase+1
        if kind=='features' and versions is not None and phase%2==0:
            live_cursor=_live_cursors.get(identity,0)
            for _ in pairs:
                pair=pairs[live_cursor%len(pairs)];live_cursor+=1
                _live_cursors[identity]=live_cursor
                if pair in waiting or pair in jobs or pair not in checkpoints or versions.get(pair)!=signature:continue
                s,t=pair;through=checkpoints[pair]
                # At most thirteen indexed rows: no full-history COUNT scans.
                rows=raw.execute('SELECT open_time FROM klines WHERE symbol=? AND interval=? AND open_time>? ORDER BY open_time LIMIT 13',(s,t,through)).fetchall()
                if not 0<len(rows)<=12:continue
                # Do not step beyond the actually downloaded historical prefix.
                limit=history.get(pair)
                if limit is not None and rows[0][0]>=limit:continue
                return pair
        for _ in pairs:
            pair=pairs[cursor%len(pairs)];cursor+=1;_service_cursors[identity]=cursor
            s,t=pair
            if pair in waiting:continue
            if kind=='downloads':
                if pair in history or not raw.execute('SELECT 1 FROM klines WHERE symbol=? AND interval=? LIMIT 1',pair).fetchone():return pair
            else:
                if pair in jobs or versions is not None and pair in checkpoints and versions.get(pair)!=signature:return pair
                limit=history.get(pair)
                sql='SELECT 1 FROM klines WHERE symbol=? AND interval=? AND open_time>?'
                args=[s,t,checkpoints.get(pair,-1)]
                if limit is not None:sql+=' AND open_time<?';args.append(limit)
                if raw.execute(sql+' LIMIT 1',args).fetchone():return pair
    return None


def pending_feature_pair(symbol,interval):
    """Indexed pending-state check for an optional operator recovery preference."""
    if not klines_store.DB_PATH.exists():return False
    pair=(symbol,interval)
    with closing(sqlite3.connect(klines_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as raw:
        latest=raw.execute('SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=?',pair).fetchone()[0]
    if latest is None:return False
    if not features_store.DB_PATH.exists():return True
    with closing(sqlite3.connect(features_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as features:
        tables={r[0] for r in features.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'feature_replay_jobs' in tables and features.execute('SELECT 1 FROM feature_replay_jobs WHERE symbol=? AND interval=?',pair).fetchone():return True
        if 'feature_engine_state' not in tables:return True
        row=features.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',pair).fetchone()
        if not row or row[0] is None or row[0]<latest:return True
        if 'feature_calculation_versions' not in tables:return True
        from Section_4_Features.execution.components import current_signature
        version=features.execute('SELECT signature FROM feature_calculation_versions WHERE symbol=? AND interval=?',pair).fetchone()
        return not version or version[0]!=current_signature()
