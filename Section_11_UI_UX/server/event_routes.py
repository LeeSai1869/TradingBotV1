"""Authenticated, read-only historical research events."""
from urllib.parse import parse_qs
from Section_1_Global_Core import event_history,btc_strategy_history,pivot_research
from Section_5_Market_Regime.events import catalog


def handle_get(path,query):
    if path=='/api/pivots/context':
        qs=parse_qs(query)
        try:
            return 200,pivot_research.case_context(qs.get('symbol',['BTCUSDT'])[0],qs.get('interval',['15m'])[0],qs.get('id',[''])[0],int(qs.get('known',['0'])[0]),source_id=qs.get('source',[''])[0],before=int(qs.get('before',['12'])[0]),after=int(qs.get('after',['24'])[0]),as_of=int(qs['as_of'][0]) if 'as_of' in qs else None)
        except (ValueError,TypeError) as error:return 400,dict(error=str(error))
        except RuntimeError as error:return 409,dict(error=str(error))
    if path=='/api/events/catalog':return 200,catalog.definitions()
    if path=='/api/strategy/btc':
        qs=parse_qs(query)
        try:return 200,btc_strategy_history.history(qs.get('symbol',['BTCUSDT'])[0],qs.get('interval',['5m'])[0],before=int(qs['before'][0]) if 'before' in qs else None,days=int(qs.get('days',['90'])[0]))
        except (ValueError,TypeError) as error:return 400,dict(error=str(error))
    if path!='/api/events/history':return None,None
    qs=parse_qs(query)
    try:
        limit=int(qs.get('limit',['250'])[0]);before=qs.get('before',[None])[0]
        return 200,event_history.history(qs.get('symbol',['BTCUSDT'])[0],qs.get('interval',['5m'])[0],limit=limit,before=int(before) if before is not None else None)
    except (ValueError,TypeError) as error:return 400,dict(error=str(error))
