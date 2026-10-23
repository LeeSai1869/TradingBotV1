"""One symbol owns historical download/replay work; live refreshes stay independent."""
from contextlib import closing
import sqlite3
from .memory_storage.Storage import klines_store,features_store

_selected=None
_identity=None


def work_symbol(symbols,intervals):
    """Keep the current symbol until its raw history and feature checkpoints finish.

    Existing symbols retain registry order ahead of empty symbols. Never use feature
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
        checkpoints={};versions=None;jobs=set()
        if features_store.DB_PATH.exists():
            with closing(sqlite3.connect(f'file:{features_store.DB_PATH}?mode=ro',uri=True,timeout=2)) as features:
                if features.execute("SELECT 1 FROM sqlite_master WHERE name='feature_engine_state'").fetchone():
                    checkpoints={(s,t):v for s,t,v in features.execute('SELECT symbol,interval,last_open_time FROM feature_engine_state')}
                if features.execute("SELECT 1 FROM sqlite_master WHERE name='feature_calculation_versions'").fetchone():
                    from Section_4_Features.execution.components import current_signature
                    signature=current_signature()
                    versions={(s,t):v for s,t,v in features.execute('SELECT symbol,interval,signature FROM feature_calculation_versions')}
                    jobs=set(features.execute('SELECT symbol,interval FROM feature_replay_jobs'))
        def pending(s):
            for t in intervals:
                if (s,t) in history or (s,t) in jobs or versions is not None and versions.get((s,t))!=signature:return True
                # Indexed point lookup; never scan millions of candles per cycle.
                latest=raw.execute('SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=?',(s,t)).fetchone()[0]
                if latest is None or checkpoints.get((s,t),-1)<latest:return True
            return False
        if _selected in symbols and pending(_selected):return _selected
        existing=[s for s in symbols if raw.execute('SELECT 1 FROM klines WHERE symbol=? LIMIT 1',(s,)).fetchone()]
        _selected=next((s for s in existing+[s for s in symbols if s not in existing] if pending(s)),None)
    return _selected


def owns_history(symbol):
    return _selected is None or _selected==symbol
