"""Read-only evidence annotation; does not alter DI decisions or candle memory."""
import time
from .engine import evaluate as confidence
from Section_10_Opportunity_Engine.engine import evaluate as opportunity


def annotate(bars,*,fee_bps=4.,slippage_bps=2.,now_ms=None):
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    closed=[bar for bar in bars if not bar.get('provisional') and bar['client']['close_time']<now_ms]
    latest=closed[-1] if closed else None
    for bar in bars:
        features=bar.get('features') or {};client=bar['client']
        bar['confidence']=None;bar['opportunity']=None
        if bar.get('provisional') or client['close_time']>=now_ms or features.get('formula_version')!=3:continue
        bar['confidence']=confidence(client['close'],features)
        if bar is latest or (bar.get('momentum') or {}).get('signal_type') in ('BUY','SELL'):
            bar['opportunity']=opportunity(client['close'],features,fee_bps=fee_bps,slippage_bps=slippage_bps)
    return bars
