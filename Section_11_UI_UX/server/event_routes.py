"""Authenticated, read-only historical research events."""
from urllib.parse import parse_qs
from Section_1_Global_Core import event_history,btc_strategy_history
from Section_5_Market_Regime.events import catalog


def handle_get(path,query):
    if path=='/api/events/catalog':return 200,catalog.definitions()
    if path=='/api/strategy/btc':
        qs=parse_qs(query)
        try:return 200,btc_strategy_history.history(qs.get('symbol',['BTCUSDT'])[0],qs.get('interval',['5m'])[0],before=int(qs['before'][0]) if 'before' in qs else None)
        except (ValueError,TypeError) as error:return 400,dict(error=str(error))
    if path!='/api/events/history':return None,None
    qs=parse_qs(query)
    try:
        limit=int(qs.get('limit',['250'])[0]);before=qs.get('before',[None])[0]
        return 200,event_history.history(qs.get('symbol',['BTCUSDT'])[0],qs.get('interval',['5m'])[0],limit=limit,before=int(before) if before is not None else None)
    except (ValueError,TypeError) as error:return 400,dict(error=str(error))
