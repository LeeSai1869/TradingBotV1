"""Bounded, read-only as-of seed for Core's opportunity zone projection.

Reversible SR/OB events undo a committed checkpoint; FVG births are read from
stored qualified outputs. An incomplete history is explicitly partial.
"""
import json
from . import features_store
from ... import opportunity_inventory as projection

COLUMNS=('sr_zone_events','ob_zone_events','qualified_bull_fvg','qualified_bear_fvg',
         'bull_fvg_low','bull_fvg_high','bear_fvg_low','bear_fvg_high')
LIMIT=10000


def read_seed(raw,features,symbol,interval,before,epochs):
    rows=raw.execute('SELECT open_time,high,low,close,close_time FROM klines WHERE symbol=? AND interval=? AND open_time<? ORDER BY open_time DESC LIMIT ?',
                     (symbol,interval,before,LIMIT+1)).fetchall()
    truncated=len(rows)>LIMIT;rows=list(reversed(rows[:LIMIT]))
    inventory=projection.Inventory()
    if rows:
        values=features_store.read_replay_inputs(features,symbol,interval,rows[0][0],before,COLUMNS)
        features_store.mask_replays(features,symbol,interval,values)
        by_time={v['open_time']:v for v in values}
        inventory.coverage={k:'partial: bounded history' if truncated else 'complete stored history' for k in ('sr','ob','fvg')}
        for opened,high,low,close,closed in rows:
            inventory.advance(dict(open_time=opened,high=high,low=low,close=close,close_time=closed),by_time.get(opened,{}) if by_time.get(opened,{}).get('formula_version')==3 else {})
    # Recover older active SR/OB zones without ever exposing checkpoint-future births.
    exists=features.execute("SELECT 1 FROM sqlite_master WHERE name='feature_engine_state'").fetchone()
    saved=features.execute('SELECT last_open_time,state FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone() if exists else None
    if not saved or saved[0]<before:return inventory.export()
    try:
        state=json.loads(saved[1])
        if state.get('version')!=3 or state.get('epoch')!=list(epochs):return inventory.export()
        persistent=state['state']['persistent']
        raw_rows=raw.execute('SELECT open_time,close_time FROM klines WHERE symbol=? AND interval=? AND open_time>=? AND open_time<=? ORDER BY open_time LIMIT ?',
            (symbol,interval,before,saved[0],LIMIT+1)).fetchall()
        if not raw_rows or len(raw_rows)>LIMIT or raw_rows[0][0]!=before or any(b[0]!=a[1]+1 for a,b in zip(raw_rows,raw_rows[1:])):return inventory.export()
        events=features_store.read_replay_inputs(features,symbol,interval,before,saved[0]+1,COLUMNS[:2])
        if len(events)>LIMIT:return inventory.export()
        features_store.mask_replays(features,symbol,interval,events)
        for family,field,key in (('sr','sr_zone_events','srDisplayPrevious'),('ob','ob_zone_events','obDisplayZones')):
            if key not in persistent or not events or events[-1]['open_time']!=saved[0]:continue
            zones=dict(persistent[key]);valid=True
            for row in reversed(events):
                try:
                    changes=json.loads(row[field])
                    for event in reversed(changes):
                        identity=str(event['id'])
                        if 'before' not in event:raise ValueError()
                        if event['before'] is None:zones.pop(identity,None)
                        else:zones[identity]=event['before']
                except (KeyError,TypeError,ValueError):valid=False;break
            # Require contiguous raw coverage as well as valid reversible records.
            if not valid or [r['open_time'] for r in events]!=[r[0] for r in raw_rows]:continue
            inventory.zones={k:v for k,v in inventory.zones.items() if not k.startswith(family+':')}
            inventory.zones.update({family+':'+str(k):{**v,'family':v.get('kind','ob') if family=='ob' else 'sr'} for k,v in zones.items()})
            inventory.coverage[family]='checkpoint reversed to reference'
    except (KeyError,TypeError,ValueError):pass
    return inventory.export()
