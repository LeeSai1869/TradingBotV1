"""Bounded comparison snapshots from the combined storage gateway."""
import math
import re
import time
from urllib.parse import parse_qs
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import db, features_store
from Section_1_Global_Core.memory_storage.market_data.update_klines import INTERVAL_MS
from .settings_catalog import read_coin_catalog

FIELDS = {f'client.{key}': key.capitalize() for key in ('open','high','low','close','volume')}
FIELDS.update({f'features.{key}': key.replace('_',' ').upper()
               for key in features_store.COLUMNS if key not in {'symbol','interval','open_time'}})
FIELDS.update({'adcn.signal_type':'Signal','adcn.final_score':'Signal score'})


def handle_get(path, raw_qs):
    if path == '/api/hud/catalog':
        registry = read_coin_catalog()
        symbols = sorted({row['symbol'] for rows in registry.values() for row in rows})
        return 200, {'fields':FIELDS,'symbols':symbols,'intervals':data_policy.INTERVALS}
    if path != '/api/hud':
        return None, None
    qs = parse_qs(raw_qs)
    symbol = qs.get('symbol',[''])[0].upper()
    intervals = qs.get('intervals',['15m,1h,4h'])[0].split(',')
    fields = qs.get('fields',['features.rsi,features.adx'])[0].split(',')
    if (not re.fullmatch(r'[A-Z0-9]{2,30}',symbol) or not 1 <= len(intervals) <= 8
            or len(set(intervals)) != len(intervals) or any(iv not in data_policy.INTERVALS for iv in intervals)
            or not 1 <= len(fields) <= 20 or len(set(fields)) != len(fields) or any(f not in FIELDS for f in fields)):
        return 400, {'error':'Choose a symbol, 1–8 distinct timeframes and 1–20 supported feature rows.'}
    now = int(time.time()*1000)
    columns = []
    with data_policy.locked(timeout=1):
        for interval in intervals:
            bars = db.read_state_page(symbol,interval,1)['bars']
            bar = bars[-1] if bars else None
            values = {}
            for field in fields:
                group, key = field.split('.',1)
                value = (bar.get(group) or {}).get(key) if bar else None
                values[field] = None if isinstance(value,float) and not math.isfinite(value) else value
            close_time = bar['client']['close_time'] if bar else None
            columns.append({'interval':interval,'open_time':bar['open_time'] if bar else None,
                            'close_time':close_time,'values':values,
                            'active':data_policy.enabled(symbol,interval),
                            'stale':close_time is not None and now-close_time > 2*INTERVAL_MS[interval],
                            'status':'stored closed candle' if bar else 'waiting for downloaded candles'})
    return 200, {'symbol':symbol,'as_of':now,'fields':fields,'columns':columns}
