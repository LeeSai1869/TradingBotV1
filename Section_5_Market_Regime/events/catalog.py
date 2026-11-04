"""Causal projection of existing feature events and closed-candle candidates.

No pivot/DI indicator is recalculated. Candidate observations never imply a trade
or a confirmed swing. First-window observations seed comparisons silently.
"""
from copy import deepcopy
import hashlib
import json
import math

VERSION='research-events-v1'
TIMEFRAMES=('1m','5m','15m','30m','1h')
CHANNELS=('di_plus','di_minus','di_signed_spread')
FIELDS=('measurement_version','measurement_config_id','measurement_gap','structure_events','structure_events_version','structure_event_status','di_anchor_events','di_anchor_continuous','candidate_pivot',
        'candidate_pivot_high_price','candidate_pivot_high_bar','candidate_pivot_high_time','candidate_pivot_low_price','candidate_pivot_low_bar','candidate_pivot_low_time',
        *CHANNELS,*(channel+'_candidate_'+kind for channel in CHANNELS for kind in ('high','low')))
CATALOG={}
for family in ('STRUCTURE','DI'):
    for kind in ('HIGH','LOW'):
        for change in ('STARTED','UPDATED','CLEARED'):
            CATALOG[family+'_CANDIDATE_'+kind+'_'+change]=dict(family=family,stage='CANDIDATE',description='Closed-candle candidate '+change.lower()+'. Clearing is not proof of invalidation; a candidate may confirm or change phase.')
for kind in ('HIGH','LOW'):
    CATALOG['STRUCTURE_PIVOT_'+kind+'_CONFIRMED']=dict(family='STRUCTURE',stage='CONFIRMED',description='Existing structure confirmation; origin and knowledge time remain separate.')
    CATALOG['DI_'+kind+'_CONFIRMED']=dict(family='DI',stage='CONFIRMED',description='Existing DI-anchor reversal/spacing rules, not every one-bar wiggle. Qualification remains a separate flag.')
    CATALOG['PRICE_'+kind+'_ANCHOR_LINKED']=dict(family='DI',stage='REFERENCE',description='Existing price anchor linked by Momentum; not another structural pivot confirmation.')
for kind in ('BOS','CHOCH'):
    CATALOG['STRUCTURE_'+kind]=dict(family='STRUCTURE',stage='CONFIRMED',description='Existing structure event, never a newly inferred break.')


def definitions():return dict(version=VERSION,timeframes=list(TIMEFRAMES),events=deepcopy(CATALOG))
def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def timestamp(v):return type(v) is int and v>=0


def event(identity,type_,current,origin,value,channel,details,source_id=None):
    result=dict(type=type_,family=CATALOG[type_]['family'],stage=CATALOG[type_]['stage'],symbol=identity['symbol'],timeframe=identity['timeframe'],
        observed_open=current['open_time'],known_time=current['close_time']+1,origin_time=origin,value=value,channel=channel,details=deepcopy(details),source_id=source_id,
        catalog_version=VERSION,units='indicator_points' if channel else 'USDT' if value is not None else None,source_identity=dict(generation_id=identity.get('generation_id'),catalog_version=VERSION,venue=identity.get('venue'),market=identity.get('market')),availability='RECONSTRUCTED_CLOSE_NOT_ACTUAL_PUBLICATION')
    result['id']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return result


def candidates(row):
    values=row['features'];result={}
    direction=values.get('candidate_pivot')
    for kind,sign in (('high',1),('low',-1)):
        root='candidate_pivot_'+kind;value=values.get(root+'_price');origin=values.get(root+'_time');bar=values.get(root+'_bar')
        if direction==sign and finite(value) and value>0 and finite(origin) and origin>=0 and origin<=row['open_time'] and int(origin)==origin and finite(bar) and bar>=0:
            result[('STRUCTURE',kind,None)]=dict(value=value,origin_time=int(origin),origin_bar=bar)
    for channel in CHANNELS:
        for kind in ('high','low'):
            value=values.get(channel+'_candidate_'+kind)
            if finite(value):result[('DI',kind,channel)]=dict(value=value,origin_time=None,origin_bar=None)
    return result


def parse_array(value):
    if value is None:return []
    parsed=json.loads(value) if isinstance(value,str) else value
    if not isinstance(parsed,list) or len(parsed)>64:raise ValueError('Invalid source event array')
    if any(not isinstance(item,dict) for item in parsed):raise ValueError('Invalid source event record')
    # Reject nonfinite/unserializable payloads before deriving IDs.
    json.dumps(parsed,allow_nan=False)
    return parsed


def project(identity,current,previous=None):
    """Each result is known on current close; no retrospective peak entry."""
    if identity['timeframe'] not in TIMEFRAMES:raise ValueError('Unsupported research timeframe')
    if not timestamp(current['open_time']) or not timestamp(current['close_time']) or current['close_time']<current['open_time']:raise ValueError('Invalid closed-candle times')
    output=[];warnings=[];features=current['features'];known=current['close_time']+1
    contiguous=(previous is not None and previous['close_time']+1==current['open_time'] and not features.get('measurement_gap'))
    if contiguous:
        before=candidates(previous);after=candidates(current)
        for key in sorted(set(before)|set(after),key=str):
            old,new=before.get(key),after.get(key)
            if old==new:continue
            family,kind,channel=key
            if family=='DI' and (previous['features'].get('di_anchor_continuous') not in (True,1) or features.get('di_anchor_continuous') not in (True,1)):continue
            if family=='STRUCTURE' and (previous['features'].get('candidate_pivot') not in (-1,0,1) or features.get('candidate_pivot') not in (-1,0,1)):continue
            # DI candidate origin timestamps are not exported by the producer.
            # Do not manufacture an origin from the observation candle.
            change='STARTED' if old is None else 'CLEARED' if new is None else 'UPDATED'
            value=new or old
            output.append(event(identity,f'{family}_CANDIDATE_{kind.upper()}_{change}',current,value['origin_time'],value['value'],channel,dict(previous=old,current=new,meaning='Candidate observation; not a confirmed pivot or BUY/SELL')))
    elif previous is not None:warnings.append('Candidate comparison suppressed across a gap')
    for field in ('structure_events','di_anchor_events'):
        try:records=parse_array(features.get(field))
        except (ValueError,TypeError):warnings.append(field+': malformed source');continue
        if field=='structure_events' and (features.get('structure_events_version')!='structure-events-v1' or features.get('structure_event_status')!='READY'):
            if records:warnings.append('Structure lineage is not ready')
            continue
        for record in records:
            type_=record.get('type')
            if not isinstance(type_,str):warnings.append('Unknown source event type');continue
            origin=record.get('origin_time' if field=='structure_events' else 'time');source_known=record.get('known_time' if field=='structure_events' else 'confirmed_time')
            if field=='structure_events':
                normalized={'PIVOT_HIGH':'STRUCTURE_PIVOT_HIGH_CONFIRMED','PIVOT_LOW':'STRUCTURE_PIVOT_LOW_CONFIRMED','BOS':'STRUCTURE_BOS','CHOCH':'STRUCTURE_CHOCH'}.get(type_)
            else:
                normalized={'di_high':'DI_HIGH_CONFIRMED','di_low':'DI_LOW_CONFIRMED','price_high':'PRICE_HIGH_ANCHOR_LINKED','price_low':'PRICE_LOW_ANCHOR_LINKED'}.get(type_)
                if type_ in ('price_high','price_low'):source_known=record.get('known_time')
            if normalized is None:continue
            if normalized.startswith('DI_') and features.get('di_anchor_continuous') not in (True,1):
                warnings.append('DI anchor continuity unavailable');continue
            if normalized.startswith(('STRUCTURE_PIVOT_','DI_','PRICE_')) and origin is None:
                warnings.append('Source origin unavailable');continue
            if source_known!=known or type(source_known) is not int or origin is not None and (not timestamp(origin) or origin>current['open_time']):
                warnings.append(field+': future/invalid source times');continue
            if normalized.startswith('DI_') and record.get('channel') not in CHANNELS:
                warnings.append('Unknown DI channel');continue
            value=record.get('value',record.get('price'))
            if (normalized.startswith(('STRUCTURE_PIVOT_','DI_','PRICE_')) and not finite(value)) or value is not None and not finite(value):warnings.append('Invalid source value');continue
            output.append(event(identity,normalized,current,origin,value,record.get('channel'),record,record.get('id')))
    return list({item['id']:item for item in output}.values()),sorted(set(warnings))
