"""Read-only Volume Profile checkpoint/node diagnostics; no recalculation or fetch."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
import time

from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import features_store,klines_store
from Section_11_UI_UX.server import volume_profile


def stamp(value):
    return datetime.fromtimestamp(value/1000,timezone.utc).isoformat() if value is not None else 'none'


def report(symbol,intervals,*,now_ms=None):
    now=int(time.time()*1000) if now_ms is None else now_ms
    result=dict(symbol=symbol,candle_database=str(Path(klines_store.DB_PATH).resolve()),
                feature_database=str(Path(features_store.DB_PATH).resolve()),as_of=now,frames=[])
    policy=data_policy.read();epoch=[policy['epochs'].get('symbol:'+symbol,0)]
    raw=features=None
    try:
        if klines_store.DB_PATH.is_file():
            raw=sqlite3.connect(klines_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=2);raw.execute('BEGIN')
        if features_store.DB_PATH.is_file():
            features=sqlite3.connect(features_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=2);features.execute('BEGIN')
        for interval in intervals:
            row=dict(timeframe=interval,active=data_policy.enabled(symbol,interval),latest_closed=None,feature_checkpoint=None)
            result['frames'].append(row)
            try:
                last=raw.execute('SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=? AND close_time<?',(symbol,interval,now)).fetchone()[0] if raw else None
                row['latest_closed']=last
                checkpoint=features.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone() if features else None
                row['feature_checkpoint']=checkpoint[0] if checkpoint else None
                f=features_store.read_row(features,symbol,interval,last) if features and last is not None else None
                latest=dict(open_time=last,features=f or {}) if last is not None else None
                key=':'.join(map(str,epoch+[policy['epochs'].get('interval:'+interval,0)]))
                snapshot=volume_profile.snapshot(symbol,interval,latest,key)
                bins=snapshot.get('bins',[]);positive=[b for b in bins if b['volume']>0]
                nodes=Counter(b['node'] for b in positive)
                row.update(status=snapshot['status'],stale=snapshot.get('stale',False),reason=snapshot.get('reason'),as_of=snapshot.get('as_of'),lookback=snapshot.get('lookback'),
                           levels=snapshot.get('levels') or {key:(f or {}).get(key) for key in ('vp_poc','vp_va_low','vp_va_high')},
                           bins=len(bins),positive_bins=len(positive),high_volume_nodes=nodes['high'],low_volume_nodes=nodes['low'],
                           zero_volume_bins=len(bins)-len(positive))
            except (OSError,ValueError,KeyError,sqlite3.Error) as error:
                row.update(status='unavailable',reason=str(error))
        return result
    finally:
        if raw:raw.close()
        if features:features.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('symbol',nargs='?',default='BTCUSDT')
    parser.add_argument('--intervals',nargs='+',choices=data_policy.INTERVALS,default=['5m','15m','30m','1h','4h'])
    parser.add_argument('--json',action='store_true');args=parser.parse_args()
    value=report(args.symbol.upper(),args.intervals)
    if args.json:print(json.dumps(value,indent=2,allow_nan=False));return
    print('Feature database:',value['feature_database'])
    print('VP histogram/node checkpoint diagnostics (closed candles only; no data written):')
    for row in value['frames']:
        print(f'{row["timeframe"]}: {row["status"]}{" (last completed profile; updating)" if row.get("stale") else ""} | {"ACTIVE" if row["active"] else "PAUSED"}')
        print(f'  Closed candle: {stamp(row["latest_closed"])} | feature checkpoint: {stamp(row["feature_checkpoint"])}')
        if row.get('reason'):print('  Reason:',row['reason'])
        else:print(f'  Histogram: {row["bins"]} bins; nonzero HVN={row["high_volume_nodes"]}, LVN={row["low_volume_nodes"]}; zero-volume bins={row["zero_volume_bins"]}; lookback={row["lookback"]}')
        if row.get('as_of') is not None:print('  Profile source candle:',stamp(row['as_of']))
        print('  Levels:',json.dumps(row.get('levels',{}),sort_keys=True))
    print('Ready bins with missing chart nodes indicate a display/settings/backend-profile issue, not absent VP calculation. Zero-volume bins have no histogram width.')


if __name__=='__main__':main()
