"""Closed Binance candle boundaries, including Monday weeks/calendar months."""
from datetime import datetime, timezone, timedelta
from Section_1_Global_Core.aggregation_processor import advance

FRAMES = {'1m':60000,'3m':180000,'5m':300000,'15m':900000,'30m':1800000,
          '1h':3600000,'2h':7200000,'4h':14400000,'6h':21600000,'8h':28800000,
          '12h':43200000,'1d':86400000,'3d':259200000,'1w':604800000,'1M':None}


def end(opened, frame):
    return advance(opened,frame)


def latest_closed(known, frame):
    if frame=='1M':
        dt=datetime.fromtimestamp(known/1000,timezone.utc).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
        return int((dt-timedelta(days=1)).replace(day=1).timestamp()*1000)
    if frame=='1w':
        dt=datetime.fromtimestamp(known/1000,timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
        return int((dt-timedelta(days=dt.weekday()+7)).timestamp()*1000)
    step=FRAMES[frame]
    return known//step*step-step
