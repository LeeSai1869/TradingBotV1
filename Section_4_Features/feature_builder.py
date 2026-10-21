"""Build the complete translated Section 4/5 packet from chronological raw bars.

Pass an Engine for streaming updates. Without one, df must contain the complete
history prefix to reproduce recursive indicators and stateful zone lifecycles.
There is no rolling-window approximation in the runner.
"""
from Section_4_Features.feature_packet import create_feature_packet
from Section_4_Features.execution.engine import Engine


def build_feature_packet(*,tf,symbol,df=None,client=None,engine=None,bar_index=None,is_confirmed=True,
                         pivot_high=None,pivot_low=None,is_realtime=False,daily_bars=None):
    if client is None and (df is None or df.empty):return create_feature_packet(tf=tf,features={},valid=False)
    current=engine or Engine(symbol,tf)
    if client is not None:
        clients=[client]
    else:
        rows=df.to_dict('records')
        if engine is not None:rows=rows[-1:]
        clients=[]
        for row in rows:
            timestamp=int(row.get('time',row.get('bar_time',row.get('open_time'))))
            if 'close_time' in row:end=int(row['close_time'])
            else:
                from Section_1_Global_Core.memory_storage.market_data.update_klines import INTERVAL_MS
                if tf=='1M':
                    from datetime import datetime,timezone
                    date=datetime.fromtimestamp(timestamp/1000,timezone.utc);end=int(date.replace(year=date.year+(date.month==12),month=date.month%12+1).timestamp()*1000)-1
                else:end=timestamp+INTERVAL_MS[tf]-1
            clients.append(dict(symbol=symbol,interval=tf,open_time=timestamp,close_time=end,**{k:float(row[k]) for k in ('open','high','low','close','volume')}))
    result=None
    for bar in clients:result=current.step(bar,is_confirmed=is_confirmed,is_realtime=is_realtime,daily_bars=daily_bars)
    return create_feature_packet(tf=tf,features=result,valid=result is not None)
