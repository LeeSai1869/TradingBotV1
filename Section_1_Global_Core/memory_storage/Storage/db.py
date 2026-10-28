"""
================================================================================
CENTRAL DB ACCESS — the one place every section reads and writes through.
================================================================================

Wraps the three stores (klines_store, features_store, adcn_store).
Each store owns its schema; this module owns the *access pattern*.

Every caller uses:
    from Section_1_Global_Core.memory_storage.Storage import db

    db.write_klines([...])
    db.read_last_klines("BTCUSDT", "15m", 500)
    db.write_features([...])
    db.read_features_after("BTCUSDT", "15m", since_ms)
    ...

No section opens sqlite3 directly. No section imports the stores
directly. Everything goes through db.py.
================================================================================
"""

from __future__ import annotations
from pathlib import Path
import sqlite3
from contextlib import ExitStack,closing

from . import klines_store
from . import features_store
from . import adcn_store


# ==============================================================================
# PATHS
# ==============================================================================

KLINES_DB   = klines_store.DB_PATH
FEATURES_DB = features_store.DB_PATH
ADCN_DB     = adcn_store.DB_PATH


# ==============================================================================
# KLINES
# ==============================================================================

def write_klines(rows: list[dict]) -> int:
    """Insert a batch of kline rows. Returns number of rows written."""
    conn = klines_store.open_db()
    try:
        return klines_store.insert_rows(conn, rows)
    finally:
        conn.close()


def read_klines(symbol, interval, start_ms=None, end_ms=None):
    """Read klines in [start_ms, end_ms)."""
    conn = klines_store.open_db()
    try:
        return klines_store.read_range(conn, symbol, interval, start_ms, end_ms)
    finally:
        conn.close()


def read_last_klines(symbol, interval, n):
    """Read the last N closed bars, oldest first."""
    conn = klines_store.open_db()
    try:
        return klines_store.read_last_n(conn, symbol, interval, n)
    finally:
        conn.close()


def read_klines_after(symbol, interval, after_open_ms):
    """Read every closed bar with open_time > after_open_ms."""
    conn = klines_store.open_db()
    try:
        return klines_store.read_after(conn, symbol, interval, after_open_ms)
    finally:
        conn.close()


def read_klines_tail(symbol, interval, end_ms, n=500):
    conn = klines_store.open_db()
    try:
        return klines_store.read_page(conn, symbol, interval, n, before=end_ms)
    finally:
        conn.close()


def read_state_after(symbol, interval, after_ms, limit=500):
    conn = klines_store.open_db()
    try:
        rows = klines_store.read_after_page(conn, symbol, interval, after_ms, limit)
    finally:
        conn.close()
    if not rows:
        return []
    return read_state_range(symbol, interval, int(rows[0][2]), int(rows[-1][2]) + 1)


def last_kline_time(symbol, interval):
    conn = klines_store.open_db()
    try:
        return klines_store.last_open_time(conn, symbol, interval)
    finally:
        conn.close()


def count_klines(symbol=None, interval=None):
    conn = klines_store.open_db()
    try:
        return klines_store.count_rows(conn, symbol, interval)
    finally:
        conn.close()


# ==============================================================================
# FEATURES
# ==============================================================================

def write_features(rows: list[dict]) -> int:
    """Insert a batch of feature rows. Returns number of rows written."""
    conn = features_store.open_db()
    try:
        return features_store.insert_rows(conn, rows)
    finally:
        conn.close()


def read_features(symbol, interval, open_time):
    conn = features_store.open_db()
    try:
        return features_store.read_row(conn, symbol, interval, open_time)
    finally:
        conn.close()


def last_feature_time(symbol, interval):
    conn = features_store.open_db()
    try:
        return features_store.last_open_time(conn, symbol, interval)
    finally:
        conn.close()


def count_features(symbol=None, interval=None):
    conn = features_store.open_db()
    try:
        return features_store.count_rows(conn, symbol, interval)
    finally:
        conn.close()


# ==============================================================================
# CANONICAL PER-BAR STATE
# ==============================================================================

_KLINE_COLUMNS = (
    "symbol", "interval", "open_time",
    "open", "high", "low", "close", "volume", "close_time",
)


def read_state_range(symbol, interval, start_ms, end_ms):
    """
    Read canonical permanent state in [start_ms, end_ms).

    Klines are the authoritative timeline. Each returned item represents
    exactly one stored kline. Permanent features and permanent ADCN state
    are attached by the shared identity:

        (symbol, interval, open_time)

    Missing derived rows remain None; they never remove a canonical bar.
    The three physical stores remain an implementation detail of this
    public Central Core contract.
    """
    with ExitStack() as stack:
        k_conn=stack.enter_context(closing(klines_store.open_db()))
        f_conn=stack.enter_context(closing(features_store.open_db()))
        a_conn=stack.enter_context(closing(adcn_store.open_db()))
        kline_rows = klines_store.read_range(
            k_conn, symbol, interval, start_ms, end_ms
        )
        feature_rows = features_store.read_range(
            f_conn, symbol, interval, start_ms, end_ms
        )
        adcn_rows = adcn_store.read_range(
            a_conn, symbol, interval, start_ms, end_ms
        )

    features_by_time = {
        int(row["open_time"]): row
        for row in feature_rows
    }
    adcn_by_time = {
        int(row["open_time"]): row
        for row in adcn_rows
    }

    state = []

    for raw in kline_rows:
        client = dict(zip(_KLINE_COLUMNS, raw))
        open_time = int(client["open_time"])

        state.append({
            "symbol": client["symbol"],
            "interval": client["interval"],
            "open_time": open_time,
            "client": client,
            "features": features_by_time.get(open_time),
            "adcn": adcn_by_time.get(open_time),
        })

    return state


def _read_connection(path):
    """Read committed data without schema creation or a writer connection."""
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=1)


def _read_derived(store, symbol, interval, start_ms, end_ms):
    if not store.DB_PATH.exists():
        return []
    conn = _read_connection(store.DB_PATH)
    try:
        return store.read_range(conn, symbol, interval, start_ms, end_ms)
    finally:
        conn.close()


def read_state_page(symbol, interval, limit=1000, *, before=None,fee_bps=4.,slippage_bps=2.):
    """One combined record per stored candle, with an exclusive older cursor.

    Keep the selected kline keys authoritative even while the ingestion
    process commits new rows. Missing derived rows remain None.
    """
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if not klines_store.DB_PATH.exists():
        return {"bars": [], "next_before": None}
    conn = _read_connection(klines_store.DB_PATH)
    try:
        rows = klines_store.read_page(conn, symbol, interval, limit + 2, before=before)
        cursor=klines_store.history_cursor(conn,symbol,interval)
    finally:
        conn.close()
    has_more = len(rows) > limit
    if not rows:
        return {"bars": [], "next_before": None}
    start_ms, end_ms = int(rows[0][2]), int(rows[-1][2]) + 1
    features = _read_derived(features_store, symbol, interval, start_ms, end_ms)
    decisions = _read_derived(adcn_store, symbol, interval, start_ms, end_ms)
    features_by_time = {int(row["open_time"]): row for row in features}
    decisions_by_time = {int(row["open_time"]): row for row in decisions}
    bars = []
    for row in rows:
        client = dict(zip(_KLINE_COLUMNS, row))
        open_time = int(client["open_time"])
        bars.append({
            "symbol": symbol, "interval": interval, "open_time": open_time,
            "time": open_time // 1000,
            "client": client,
            "features": features_by_time.get(open_time),
            "adcn": decisions_by_time.get(open_time),
        })
    # Two predecessor rows seed the same Section 8 gate at page boundaries.
    # This is a bounded read-only projection; it does not backfill ADCN memory.
    from Section_8_Decision_Engine.presentation import annotate
    bars=annotate(bars)
    # Most recent windows can still lack replayed features. Never search their
    # entire older history when there is no candidate to display in this page.
    if any(bar.get('momentum',{}).get('signal_type') for bar in bars[-limit:] if bar.get('momentum')):
        first_evaluated=bars[2]['open_time'] if len(bars)>2 else bars[0]['open_time']
        last_signal=read_previous_decision_candidate(symbol,interval,first_evaluated)
        bars=annotate(bars,last_signal)
    from ...analysis import annotate as evidence
    bars=evidence(bars,fee_bps=fee_bps,slippage_bps=slippage_bps)[-limit:]
    return {"bars": bars, "next_before": bars[0]['open_time'] if has_more else None, "history_pending":cursor is not None}


# ==============================================================================
# ADCN
# ==============================================================================

def write_adcn(rows: list[dict]) -> int:
    conn = adcn_store.open_db()
    try:
        return adcn_store.insert_rows(conn, rows)
    finally:
        conn.close()


def read_adcn(symbol, interval, open_time):
    conn = adcn_store.open_db()
    try:
        return adcn_store.read_row(conn, symbol, interval, open_time)
    finally:
        conn.close()


def read_signals(symbol, interval, limit=None):
    conn = adcn_store.open_db()
    try:
        return adcn_store.read_signals(conn, symbol, interval, limit)
    finally:
        conn.close()


def read_latest_adcn(symbol, interval):
    """
    Read the latest permanent ADCN row for (symbol, interval).

    Returns a dictionary keyed by adcn_store.COLUMNS, or None when
    no permanent ADCN state exists for the requested market/timeframe.
    """
    conn = adcn_store.open_db()
    try:
        last = adcn_store.last_open_time(conn, symbol, interval)
        if last is None:
            return None
        row = adcn_store.read_row(conn, symbol, interval, last)
    finally:
        conn.close()

    if row is None:
        return None

    return row


def last_adcn_time(symbol, interval):
    conn = adcn_store.open_db()
    try:
        return adcn_store.last_open_time(conn, symbol, interval)
    finally:
        conn.close()


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # paths
    "KLINES_DB", "FEATURES_DB", "ADCN_DB",

    # klines
    "write_klines", "read_klines", "read_last_klines", "read_klines_after",
    "last_kline_time", "count_klines", "read_klines_tail",

    # features
    "write_features", "read_features", "last_feature_time", "count_features",

    # adcn
    "write_adcn", "read_adcn", "read_latest_adcn", "last_adcn_time",

    # canonical state
    "read_state_range",
    "read_state_page", "read_state_after", "read_fvg_frame", "read_feature_progress", "read_sr_snapshot",
]


def read_decision_inputs(symbol,interval,after,limit=200):
    """Small closed-bar/DI projection, capped by committed feature replay state."""
    if not features_store.DB_PATH.exists() or not klines_store.DB_PATH.exists():return []
    from Section_1_Global_Core import data_policy
    with data_policy.snapshot_guard(), ExitStack() as stack:
        features=stack.enter_context(closing(_read_connection(features_store.DB_PATH)))
        raw=stack.enter_context(closing(_read_connection(klines_store.DB_PATH)))
        features.execute('BEGIN')
        through=features_store.replay_through(features,symbol,interval)
        if through is None:return []
        rows=[row for row in klines_store.read_after_page(raw,symbol,interval,after,limit) if row[2]<=through]
        if not rows:return []
        values=features_store.read_di_inputs(features,symbol,interval,rows[0][2],rows[-1][2]+1)
        return [dict(open_time=row[2],close_time=row[8],close=row[6],features=values.get(row[2])) for row in rows]



def read_decision_seed(symbol,interval):
    """Latest three raw candles at the committed feature prefix; never a live tail."""
    if not features_store.DB_PATH.exists() or not klines_store.DB_PATH.exists():return []
    from Section_1_Global_Core import data_policy
    with data_policy.snapshot_guard(), ExitStack() as stack:
        features=stack.enter_context(closing(_read_connection(features_store.DB_PATH)));raw=stack.enter_context(closing(_read_connection(klines_store.DB_PATH)))
        features.execute('BEGIN')
        through=features_store.replay_through(features,symbol,interval)
        if through is None:return []
        rows=klines_store.read_page(raw,symbol,interval,3,before=through+1)
        if not rows:return []
        values=features_store.read_di_inputs(features,symbol,interval,rows[0][2],rows[-1][2]+1)
        return [dict(open_time=row[2],close_time=row[8],close=row[6],features=values.get(row[2])) for row in rows]



def iter_decision_history(symbols=None,intervals=None):
    """Read-only, streaming canonical closed history for strategy evaluation.

    Each yielded cursor is consumed before requesting the next pair. A feature
    snapshot caps the stream at its committed replay prefix.
    """
    import time
    if not klines_store.DB_PATH.exists() or not features_store.DB_PATH.exists():return
    raw=_read_connection(klines_store.DB_PATH)
    try:
        raw.execute('ATTACH DATABASE ? AS f',(f'file:{features_store.DB_PATH}?mode=ro',))
        raw.execute('BEGIN')
        if not raw.execute("SELECT 1 FROM f.sqlite_master WHERE name='feature_engine_state'").fetchone():return
        pairs=raw.execute('SELECT symbol,interval,last_open_time FROM f.feature_engine_state ORDER BY symbol,interval').fetchall()
        for symbol,interval,cap in pairs:
            if raw.execute("SELECT 1 FROM f.sqlite_master WHERE name='feature_replay_jobs'").fetchone():
                task=raw.execute('SELECT last_time,columns FROM f.feature_replay_jobs WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                if task:
                    import json
                    if set(json.loads(task[1]))&set(features_store.decision_fields()+['c','close']):cap=min(cap,task[0])
            if (symbols and symbol not in symbols) or (intervals and interval not in intervals):continue
            columns=('open_time','close_time','open','close','di_plus','di_minus','di_spread','adx')
            cursor=raw.execute('''SELECT k.open_time,k.close_time,k.open,k.close,f.di_plus,f.di_minus,f.di_spread,f.adx
                FROM klines k JOIN f.features f ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time
                WHERE k.symbol=? AND k.interval=? AND k.open_time<=? AND k.close_time<? AND f.formula_version=3 ORDER BY k.open_time''',
                (symbol,interval,cap,int(time.time()*1000)))
            yield symbol,interval,cap,(dict(zip(columns,r)) for r in cursor)
    finally:raw.close()


def read_previous_decision_candidate(symbol,interval,before):
    """Nearest raw gate direction before a candle, using small backward pages.

    Last accepted direction equals last raw candidate direction under strict
    alternation. This seeds chart pages without restarting alternation at each
    viewport boundary, and avoids replaying every older decision into memory.
    Only the small DI/ADX projection is read; connections always close explicitly.
    """
    from contextlib import ExitStack,closing
    from Section_8_Decision_Engine.rules import di_turning_point as rule
    import time
    if not klines_store.DB_PATH.exists() or not features_store.DB_PATH.exists():return None
    now=int(time.time()*1000)
    with ExitStack() as stack:
        raw=stack.enter_context(closing(_read_connection(klines_store.DB_PATH)))
        features=stack.enter_context(closing(_read_connection(features_store.DB_PATH)))
        features.execute('BEGIN')
        while True:
            rows=klines_store.read_page(raw,symbol,interval,514,before=before)
            if len(rows)<3:return None
            values=features_store.read_di_inputs(features,symbol,interval,rows[0][2],rows[-1][2]+1)
            records=[];previous=[];last_close=None
            for row in rows:
                if last_close is not None and last_close+1!=row[2]:previous=[]
                last_close=row[8]
                if row[8]>=now or row[2] not in values:
                    previous=[];records.append(None);continue
                current={**values[row[2]],'close':row[6]}
                records.append(rule.evaluate(previous,current)['signal_type'])
                previous.append(current);previous=previous[-2:]
            for signal in reversed(records[2:]):
                if signal:return signal
            if len(rows)<514:return None
            before=rows[2][2]


FVG_COLUMNS=tuple([f'qualified_{side}_fvg' for side in ('bull','bear')]+
                  [f'{side}_fvg_{edge}' for side in ('bull','bear') for edge in ('low','high')]+
                  [f'nearest_{side}_fvg_{field}' for side in ('bull','bear') for field in ('low','high','created_bar','age')]+[f'nearest{side}_fvg_reaction_score' for side in ('bull','bear')])


def read_fvg_frame(symbol,interval,known_version=None,*,include_bars=True):
    """Bounded source-frame projection; no network, calculations or schema writes."""
    import time
    import json
    raw=_read_connection(klines_store.DB_PATH) if klines_store.DB_PATH.exists() else None
    if raw is None:return {'version':'empty','bars':[]}
    try:
        latest=raw.execute('SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()[0]
        first_close=klines_store.first_close_waits(raw,int(time.time()*1000)).get((symbol,interval))
    finally:raw.close()
    features=_read_connection(features_store.DB_PATH) if features_store.DB_PATH.exists() else None
    try:
        from Section_1_Global_Core import data_policy
        epochs=data_policy.read()['epochs']
        version=[latest,epochs.get(f'symbol:{symbol}',0),epochs.get(f'interval:{interval}',0),first_close]
        if features:
            for table,columns in [('feature_engine_state','last_open_time'),('feature_calculation_versions','signature'),('feature_replay_jobs','last_time')]:
                row=features.execute(f'SELECT {columns} FROM {table} WHERE symbol=? AND interval=?',(symbol,interval)).fetchone() if features.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone() else None
                version.append(row[0] if row else None)
        version=json.dumps(version,separators=(',',':'))
        if version==known_version:return {'version':version,'unchanged':True}
        raw=_read_connection(klines_store.DB_PATH)
        try:rows=klines_store.read_last_n(raw,symbol,interval,1000)
        finally:raw.close()
        rows=[r for r in rows if r[8]<int(time.time()*1000)]
        values=[]
        if features and rows and include_bars:
            values=features_store.read_replay_inputs(features,symbol,interval,rows[0][2],rows[-1][2]+1,FVG_COLUMNS)
            features_store.mask_replays(features,symbol,interval,values)
        by_time={r['open_time']:r for r in values}
        active=[];task=None;calculated=False
        if features and rows:
            state=features.execute('SELECT last_open_time,state FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone() if features.execute("SELECT 1 FROM sqlite_master WHERE name='feature_engine_state'").fetchone() else None
            task=features_store.pending_replay(features,symbol,interval)
            position=next((i for i,r in enumerate(rows) if state and r[2]==state[0]),None)
            if state and position is not None and not (task and any('fvg' in c for c in task[2])):
                try:
                    saved=json.loads(state[1]);s=saved['state'];arrays=s['persistent']
                    if saved.get('version')==3 and saved.get('epoch')==[epochs.get(f'symbol:{symbol}',0),epochs.get(f'interval:{interval}',0)]:
                        calculated=True
                        for side,label in [('bull','Bull'),('bear','Bear')]:
                            for zone_index,(low,high,created) in enumerate(zip(arrays.get('fvg'+label+'Low',[]),arrays.get('fvg'+label+'High',[]),arrays.get('fvg'+label+'CreatedBar',[]))):
                                age=s['index']-created
                                if not isinstance(age,int) or age<0:continue
                                birth=rows[position-age] if age<=position else rows[0]
                                if not isinstance(low,(int,float)) or not isinstance(high,(int,float)):continue
                                previous=rows[position];valid=True
                                for subsequent in rows[position+1:]:
                                    touched=subsequent[5]<=high and subsequent[4]>=low
                                    if subsequent[2]!=previous[8]+1 or touched and (subsequent[6]<low if side=='bull' else subsequent[6]>high):valid=False;break
                                    previous=subsequent
                                if not valid:continue
                                scores=arrays.get('fvg'+label+'ReactionScore',[])
                                score=scores[zone_index] if zone_index<len(scores) else None
                                active.append({'score':score,'score_time':state[0]//1000,'side':side,'low':low,'high':high,'created':created,'time':birth[2]//1000,'close_time':birth[8],'older':age>position})
                except (KeyError,TypeError,ValueError):pass
        readiness='awaiting first closed candle' if first_close is not None and latest is None else 'feature repair pending' if task and any('fvg' in c for c in task[2]) else 'ready' if calculated or any(r.get('qualified_bull_fvg') is not None or r.get('qualified_bear_fvg') is not None for r in values) else 'waiting for features'
        return {'version':version,'status':readiness,'active':active,'bars':[{'time':r[2]//1000,'open_time':r[2],
                 'client':dict(zip(_KLINE_COLUMNS,r)),'features':by_time.get(r[2])} for r in rows] if include_bars else []}
    finally:
        if features:features.close()


def read_feature_progress(symbol,interval,latest=None,*,history_pending=False):
    """Small indexed checkpoint status; row counts can contain legacy formulas."""
    result={'through':None,'latest':latest,'status':'waiting for features','repair':None}
    if not features_store.DB_PATH.exists():return result
    conn=_read_connection(features_store.DB_PATH)
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='feature_engine_state'").fetchone():return result
        row=conn.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
        result['through']=row[0] if row else None
        repair=features_store.pending_replay(conn,symbol,interval)
        if repair:
            result['repair']={'through':repair[0] if repair[0]>=0 else None,'target':repair[1],'columns':len(repair[2])}
            result['status']='updating affected features'
            result['zone_repairs']=(["FVG"] if any('fvg' in c for c in repair[2]) else [])+(["Support / Resistance"] if any('support' in c or 'resistance' in c or c=='sr_zone_events' for c in repair[2]) else [])+(['Order Blocks'] if 'ob_zone_events' in repair[2] else [])
        elif row and latest is not None and row[0]>=latest:result['status']='features current'
        elif row:result['status']='historical feature replay'
        if history_pending and result['status']!='features current':result['history_pending']=True
        return result
    finally:conn.close()


def read_sr_snapshot(symbol, interval):
    """Read committed S/R and OB identities, independently masked during repair."""
    import json
    if not features_store.DB_PATH.exists():return None
    conn=_read_connection(features_store.DB_PATH)
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='feature_engine_state'").fetchone():return None
        row=conn.execute('SELECT last_open_time,state FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
        if not row:return None
        task=features_store.pending_replay(conn,symbol,interval)
        sr_pending=bool(task and 'sr_zone_events' in task[2])
        ob_pending=bool(task and 'ob_zone_events' in task[2])
        saved=json.loads(row[1])
        from Section_1_Global_Core import data_policy
        epochs=data_policy.read()['epochs']
        if saved.get('epoch')!=[epochs.get(f'symbol:{symbol}',0),epochs.get(f'interval:{interval}',0)]:return None
        zones={} if sr_pending else saved['state']['persistent'].get('srDisplayPrevious',{})
        ob_zones={} if ob_pending else saved['state']['persistent'].get('obDisplayZones',{})
        # Scores are read from already calculated parallel arrays. Keeping them
        # out of lifecycle exports avoids a new historical formula replay.
        arrays=saved['state']['persistent'];scored={};lookup={}
        for prefix in ('support','resistance','instSupport','instResistance'):
            lookup[prefix]={str(k):v for k,v in zip(arrays.get(prefix+'ZoneIDArray',[]),arrays.get(prefix+'ScoreArray',[]))}
        for identity,zone in zones.items():
            side=zone['side'];prefix=('inst'+side.title()) if zone.get('institutional') else side
            ids=[str(value) for value in arrays.get(side+'ZoneIDArray',[])]
            index=ids.index(str(identity)) if str(identity) in ids else -1
            origins=arrays.get(side+'OriginTimeArray',[])
            touches=arrays.get(side+'TouchArray',[])
            strong=arrays.get(side+'StrongRejectArray',[])
            origin=origins[index] if 0<=index<len(origins) else None
            scored[identity]={**zone,'score':lookup[prefix].get(str(identity)),'score_time':row[0]//1000,
                'origin_time':origin//1000 if isinstance(origin,(int,float)) else None,
                'touches':touches[index] if 0<=index<len(touches) else None,
                'strong_rejections':strong[index] if 0<=index<len(strong) else None}
        valid_until=row[0]//1000;current=False
        if klines_store.DB_PATH.exists():
            candles=_read_connection(klines_store.DB_PATH)
            try:
                close=candles.execute('SELECT close_time FROM klines WHERE symbol=? AND interval=? AND open_time=?',(symbol,interval,row[0])).fetchone()
                latest=candles.execute('SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                if close:valid_until=(close[0]+1)//1000
                current=bool(latest and latest[0]==row[0] and data_policy.enabled(symbol,interval))
            finally:candles.close()
        return dict(through=row[0]//1000,valid_until=valid_until,current=current,zones=scored,ob_zones=ob_zones,status='feature repair pending' if sr_pending else 'ready')
    finally:conn.close()
