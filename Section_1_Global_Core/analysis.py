"""Read-only coordinator. Decisions, confidence and opportunity own separate rules."""
import time
import copy
from Section_9_Confidence_Engine.engine import evaluate as confidence
from Section_10_Opportunity_Engine.engine import evaluate as opportunity,with_costs
from Section_10_Opportunity_Engine.context import anchor,advance
from .opportunity_inventory import Inventory


def annotate(bars,*,fee_bps=4.,slippage_bps=2.,now_ms=None,seed=None,context_history=False,inventory_seed=None):
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    closed=[bar for bar in bars if not bar.get('provisional') and bar['client']['close_time']<now_ms]
    latest=closed[-1] if closed else None
    inventory=Inventory(inventory_seed)
    previous=None;context=copy.deepcopy(seed);prior=dict(side=seed['side'],entry=seed['entry'],open_time=seed['open_time']) if seed else None;last_close=seed.get('through_close') if seed else None
    for bar in bars:
        features=bar.get('features') or {};client=bar['client']
        bar['confidence']=None;bar['opportunity']=None;bar['signal_context']=None
        if bar.get('provisional') or client['close_time']>=now_ms:continue
        if last_close is not None and last_close+1!=bar['open_time']:
            previous=None
            if context:context={**context,'state':'coverage unknown'}
        last_close=client['close_time']
        signal=(bar.get('momentum') or {}).get('signal_type')
        saved=(bar.get('adcn') or {}).get('analysis_snapshot')
        if saved and (saved.get('side')!=signal or saved.get('open_time')!=bar['open_time'] or saved.get('entry')!=client['close']):saved=None
        if features.get('formula_version')!=3 and not saved:
            inventory.zones.clear();inventory.coverage={k:'partial: features unavailable' for k in inventory.coverage}
            previous=None
            if context:context={**context,'state':'coverage unknown'}
            if bar is latest or context_history:bar['signal_context']=context
            if bar is latest and context:bar['opportunity']=context['opportunity'];bar['confidence']=context['confidence']
            continue
        if features.get('formula_version')==3:inventory.advance(client,features)
        if signal in ('BUY','SELL'):
            bar['confidence']=copy.deepcopy(saved['confidence']) if saved else confidence(client['close'],features,previous=previous,candle=client)
        previous={**features,'close':client['close']}
        context=advance(context,bar)
        if signal in ('BUY','SELL'):
            bar['opportunity']=with_costs(saved['opportunity'],fee_bps,slippage_bps) if saved else opportunity(client['close'],features,fee_bps=fee_bps,slippage_bps=slippage_bps,
                zones=inventory.packet(bar.get('interval',''),client['close_time']+1),as_of_ms=client['close_time']+1,
                timeframe=bar.get('interval',''),inventory_status=inventory.coverage,candle=client)
        if signal in ('BUY','SELL'):
            new=anchor(bar['opportunity'],side=signal,open_time=bar['open_time'],confidence=bar['confidence'],previous=prior)
            if new:
                new['available_ms']=client['close_time']+1
                new['storage']=copy.deepcopy(saved['storage']) if saved else dict(status='reconstructed; persistence pending')
                new['storage']['display_costs_repriced']=bool(saved and saved['opportunity'].get('costs')!=bar['opportunity'].get('costs'))
                new['reference_basis']='signal candle close'
                new['signal_price']=client['close']
            if new and prior:
                new['entry_relationship']='above previous entry' if client['close']>prior['entry'] else 'below previous entry' if client['close']<prior['entry'] else 'same as previous entry'
            context=new;prior=dict(side=signal,entry=client['close'],open_time=bar['open_time'])
        if context:context={**context,'through_close':client['close_time']}
        if bar is latest and context:
            bar['opportunity']=context['opportunity'];bar['confidence']=context['confidence']
        bar['signal_context']=context if context_history or bar is latest or signal in ('BUY','SELL') else None
    return bars


def evaluate_point(client,features,previous=None):
    """Independent point snapshot. A decision label is neither accepted nor read."""
    if not features or features.get('formula_version')!=3:return None
    return dict(confidence=confidence(client['close'],features,previous=previous,candle=client),
                opportunity=opportunity(client['close'],features,candle=client))
