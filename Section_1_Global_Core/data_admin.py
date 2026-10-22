"""Validated policy changes and transactional deletion of the three memories."""
import json
from . import data_policy as policy
from .Symbols import symbols
from .memory_storage.Storage import klines_store, features_store, adcn_store

REGISTRY_FILE = symbols._SYMBOLS_JSON


def catalog():
    return json.loads(REGISTRY_FILE.read_text())


def set_timeframe(interval, status):
    if interval not in policy.INTERVALS or status not in {'active','inactive'}:
        raise ValueError('Invalid timeframe or status')
    with policy.locked():
        state = policy.read()
        state['timeframes'][interval] = status
        policy.write(state)


def set_coin(symbol, action):
    if action not in {'approve','inactive','active','disapprove'}:
        raise ValueError('Pending, staged and eligibility are determined by registry rules')
    with policy.locked():
        data = catalog()
        known = {r['symbol']: r for k in ('approved','disapproved','pending','staged','top50') for r in data.get(k, [])}
        if symbol not in known:
            raise ValueError('Unknown coin')
        entry = dict(known[symbol])
        state = policy.read()
        if action in {'approve','active'}:
            blocked = next((r for r in data['disapproved'] if r['symbol'] == symbol), {})
            if blocked.get('reason') in {'auto:meme','auto:stablecoin','not_on_binance'}:
                raise ValueError('Coin is ineligible under current registry rules')
            if symbol not in {r['symbol'] for r in data['top50']}:
                raise ValueError('Coin is outside the eligible top50; it cannot be activated')
            active = [r['symbol'] for r in data['approved'] if r['symbol'] in {r['symbol'] for r in data['top50']} and r['symbol'] not in state['paused_coins']]
            if symbol not in active and len(active) >= int(data.get('active_cap', 50)):
                raise ValueError('Active coin cap reached; make another coin inactive first')
            for key in ('approved','disapproved','pending','staged'):
                data[key] = [r for r in data.get(key, []) if r['symbol'] != symbol]
            entry.pop('reason', None)
            data['approved'].append(entry)
            state['paused_coins'] = [s for s in state['paused_coins'] if s != symbol]
        elif action == 'disapprove':
            for key in ('approved','disapproved','pending','staged'):
                data[key] = [r for r in data.get(key, []) if r['symbol'] != symbol]
            entry['reason'] = 'manual:administrator'
            data['disapproved'].append(entry)
        else:
            if symbol not in {r['symbol'] for r in data['approved']}:
                raise ValueError('Only approved coins can be made inactive')
            state['paused_coins'] = sorted(set(state['paused_coins']) | {symbol})
        tmp = REGISTRY_FILE.with_suffix('.json.admin.tmp')
        tmp.write_text(json.dumps(data, indent=2) + '\n')
        tmp.replace(REGISTRY_FILE)
        policy.write(state)
        symbols.reload()


def delete_data(*, interval=None, symbol=None):
    if (interval is None) == (symbol is None):
        raise ValueError('Choose exactly one coin or timeframe')
    if interval is not None and interval not in policy.INTERVALS:
        raise ValueError('Unknown timeframe')
    with policy.locked(), policy.snapshot_guard(exclusive=True, timeout=None):
        if symbol is not None and not any(symbol == r['symbol'] for k in ('approved','disapproved','pending','staged','top50') for r in catalog().get(k, [])):
            raise ValueError('Unknown coin')
        # Pause first. A failed delete remains paused and can safely be retried.
        state = policy.read()
        if interval:
            state['timeframes'][interval] = 'inactive'
        else:
            state['paused_coins'] = sorted(set(state['paused_coins']) | {symbol})
        scope = f'interval:{interval}' if interval else f'symbol:{symbol}'
        state['epochs'][scope] = state['epochs'].get(scope, 0) + 1
        policy.write(state)
        # Initialize derived stores using their owners; no schema duplication.
        features_store.open_db().close()
        adcn_store.open_db().close()
        conn = klines_store.open_db()
        try:
            conn.execute('ATTACH DATABASE ? AS features_memory', (str(features_store.DB_PATH),))
            conn.execute('ATTACH DATABASE ? AS decisions_memory', (str(adcn_store.DB_PATH),))
            column, value = ('interval', interval) if interval else ('symbol', symbol)
            counts = {}
            with conn:
                for name, table in [('candles','main.klines'),('features','features_memory.features'),('decisions','decisions_memory.decisions')]:
                    counts[name] = conn.execute(f'DELETE FROM {table} WHERE {column}=?', (value,)).rowcount
                conn.execute(f'DELETE FROM features_memory.feature_engine_state WHERE {column}=?', (value,))
                if conn.execute("SELECT 1 FROM sqlite_master WHERE name='history_progress'").fetchone():
                    conn.execute(f'DELETE FROM history_progress WHERE {column}=?',(value,))
            return counts
        finally:
            conn.close()
