"""Read-only selected strategy feed. No indicator computation or market activation."""
from contextlib import closing
import json
import sqlite3
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import adcn_store, strategy_store
from Section_8_Decision_Engine import strategy_registry


def snapshot(config, after, limit=100, *, armed_at=0):
    if not data_policy.enabled(config.symbol,config.interval):raise ValueError('Coin/timeframe is inactive')
    if not adcn_store.DB_PATH.is_file():raise ValueError('Strategy database is unavailable')
    with closing(sqlite3.connect(adcn_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as conn:
        conn.execute('BEGIN')
        choice=strategy_store.selected(conn,config.symbol,config.interval)
        item=choice['instance'] if choice else None
        if not item or item['id']!=config.instance_id:raise ValueError('Configured strategy is no longer selected and enabled')
        definition=strategy_registry.require(item['strategy_id'],item['version'])
        if definition.fingerprint!=item['fingerprint']:raise ValueError('Strategy fingerprint changed')
        epoch=strategy_store.epoch(config.symbol,config.interval)
        from Section_1_Global_Core.memory_storage.market_data.update_klines import INTERVAL_MS
        duration=31*86400000 if config.interval=='1M' else INTERVAL_MS[config.interval]
        # Bound the initial query to the activation candle, using the event key
        # index; never scan/replay years of archived strategy events.
        start=max(after+1,armed_at-duration)
        rows=strategy_store.events(conn,item['id'],current_epoch=epoch,start=max(0,start),limit=limit)
        return dict(epoch=epoch,events=[dict(open_time=r['open_time'],side=r['side'],**{
            'close_time':json.loads(r['payload'])['close_time']}) for r in rows])
