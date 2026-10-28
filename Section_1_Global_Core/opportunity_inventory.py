"""Project stored zone lifetimes forward; never recalculate feature formulas."""
import copy
import json
from .analysis_packet import number


class Inventory:
    def __init__(self, seed=None):
        seed=seed or {}
        self.zones=copy.deepcopy(seed.get('zones',{}))
        self.coverage=dict(seed.get('coverage',dict(sr='partial',ob='partial',fvg='partial')))
        self.last_close=seed.get('last_close')

    def advance(self, client, features):
        if self.last_close is not None and client.get('open_time',self.last_close+1)!=self.last_close+1:
            self.zones.clear();self.coverage={k:'partial: candle gap' for k in self.coverage}
        self.last_close=client['close_time']
        for family,key in (('sr','sr_zone_events'),('ob','ob_zone_events')):
            try:
                events=json.loads(features[key])
                if not isinstance(events,list):raise ValueError()
                for event in events:
                    identity=family+':'+str(event['id'])
                    if event.get('removed'):self.zones.pop(identity,None)
                    else:self.zones[identity]={**event,'family':event.get('kind','ob') if family=='ob' else 'sr'}
            except (KeyError,TypeError,ValueError):
                self.zones={k:v for k,v in self.zones.items() if not k.startswith(family+':')}
                self.coverage[family]='partial: lifecycle unavailable'
        # Stored qualified gap births plus the producer's close-through failure rule.
        for identity,z in list(self.zones.items()):
            if z['family']!='fvg':continue
            touched=client['low']<=z['high'] and client['high']>=z['low']
            if touched and (client['close']<z['low'] if z['side']=='bull' else client['close']>z['high']):self.zones.pop(identity)
        for side in ('bull','bear'):
            flag=features.get('qualified_'+side+'_fvg')
            if flag is None:
                self.zones={k:v for k,v in self.zones.items() if v['family']!='fvg' or v.get('side')!=side}
                self.coverage['fvg']='partial: qualified gaps unavailable'
                continue
            low,high=features.get(side+'_fvg_low'),features.get(side+'_fvg_high')
            if flag and number(low) and number(high) and 0<low<high:
                identity=f'fvg:{side}:{client.get("open_time",client["close_time"])}'
                self.zones[identity]=dict(family='fvg',side=side,low=low,high=high)

    def packet(self,timeframe,available_ms):
        result=[]
        for identity,z in self.zones.items():
            family=z['family'];side=z.get('side')
            role='dynamic' if family=='sr' else 'support' if side=='bull' else 'resistance'
            result.append(dict(id=identity,name=('institutional ' if z.get('institutional') else '')+identity,
                family=family,role=role,low=z.get('low'),high=z.get('high'),timeframe=timeframe,available_ms=available_ms))
        return result

    def export(self):
        return dict(zones=self.zones,coverage=self.coverage,last_close=self.last_close)
