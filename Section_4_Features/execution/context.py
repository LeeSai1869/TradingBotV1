"""Chronological feature state for one (symbol, timeframe), including TA seeds."""
from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import math
from . import runtime as rt

MANIFEST=json.loads((Path(__file__).parents[1]/'conversion/manifest.json').read_text())
HISTORY=set(MANIFEST['history']) | {'ema7','ema25','ema50','ema100','ema200','ema300','atr'}

class Context:
    def __init__(self,symbol,timeframe,parameters=None):
        from Section_2_Inputs import Inputs as inputs
        from Section_1_Global_Core.Data_Contracts_Legacy import constants, market_definitions
        self.symbol=symbol;self.timeframe=timeframe
        self.parameters={
            **{f'ema{p}Len':getattr(inputs,f'EMA_{p}_LEN') for p in (7,25,50,100,200,300)},
            'rsiLen':7,'adxLen':10,'atrLen':10,'atrMaLen':14,'srPivotLen':5,
            'fibPivotReactionATR':inputs.FIB_PIVOT_REACTION_ATR,'fvgZoneDistanceATR':inputs.FVG_ZONE_DISTANCE_ATR,
            'volumeLookback':inputs.VOLUME_LOOKBACK,'liquidityLookback':inputs.LIQUIDITY_LOOKBACK,'rangeLookback':inputs.RANGE_LOOKBACK,
            'vpLookback':inputs.VP_LOOKBACK,'vpBins':inputs.VP_BINS,'vpValueAreaPct':inputs.VP_VALUE_AREA_PCT,
            'vwapBandMultiplier1':inputs.VWAP_BAND_MULTIPLIER_1,'vwapBandMultiplier2':inputs.VWAP_BAND_MULTIPLIER_2,
            'FVG_MIN_ATR_MULT':constants.FVG_MULTIPLIER_NORMAL,'FVG_STRONG_ATR_MULT':constants.FVG_MULTIPLIER_STRONG,
            **{name:getattr(market_definitions,name) for name in ('TREND_FRESH','TREND_MATURE','TREND_WEAK','TREND_NONE','TRANSITION_NONE','TRANSITION_RISK','TRANSITION_ACTIVE')},
        }
        self.parameters.update(parameters or {})
        for key in ('rsiLen','adxLen','atrLen','atrMaLen','srPivotLen','volumeLookback','vpLookback','vpBins','liquidityLookback','rangeLookback',*[f'ema{p}Len' for p in (7,25,50,100,200,300)]):
            value=self.parameters[key]
            if type(value) is not int or not 1<=value<=5000:raise ValueError(f'{key} must be an integer from 1 to 5000')
        self.capacity=max(500,2*int(max(v for v in self.parameters.values() if isinstance(v,(int,float))))+5)
        self.persistent={};self.values={};self.histories={};self.technical={};self.calls={};self.index=-1;self.last_time=None;self.last_client=None
        self.daily_bars=[];self.day=None;self.new_day=False;self.vwap_sum=0.;self.vwap_volume=0.;self.volumes=[];self.last_regime='UNKNOWN'
    def __getitem__(self,key):
        if key in self.values:return self.values[key]
        if key in self.persistent:return self.persistent[key]
        if key in self.parameters:return self.parameters[key]
        raise KeyError(f'Unresolved Pine dependency {key!r} for {self.symbol} {self.timeframe}')
    def __setitem__(self,key,value):
        self.values[key]=value
        if key in self.persistent:self.persistent[key]=value
    def initialize(self,key,value):self.persistent[key]=value;self.values[key]=value
    def previous(self,key,index):
        if rt.is_na(index) or index<0:return rt.NA
        if index==0:return self[key]
        series=self.histories.get(key,[])
        return series[-int(index)] if len(series)>=index else rt.NA
    def input(self,title,default):return self.parameters.get(title,default)
    def begin(self,client,is_confirmed=True,is_realtime=False,is_new=True):
        timestamp=int(client['open_time'])
        if self.last_time is not None and timestamp<=self.last_time:raise ValueError('Feature bars must be strictly chronological; preview a clone for live ticks')
        self.index+=1;self.values={};self.calls={};self.is_realtime=is_realtime
        time=datetime.fromtimestamp(timestamp/1000,timezone.utc);day=time.date().isoformat();self.new_day=self.day!=day
        if self.new_day:
            self.day=day;self.vwap_sum=self.vwap_volume=0.
            self.daily_bars.append({'day':day,'open':client['open'],'high':client['high'],'low':client['low'],'close':client['close']})
            self.daily_bars=self.daily_bars[-3:]
        daily=self.daily_bars[-1];daily['high']=max(daily['high'],client['high']);daily['low']=min(daily['low'],client['low']);daily['close']=client['close']
        typical=(client['high']+client['low']+client['close'])/3
        from ..features.vwap import session_value
        from ..features.volume import moving_average
        vwap=session_value(self,client,self.new_day);volume_ma=moving_average(self,client['volume'])
        prev=self.last_client
        for field in ('open','high','low','close','volume'):
            self.values[field]=client[field];self.values['mtfData.'+field]=client[field]
            self.values['mtfData.prev'+field.capitalize()]=prev[field] if prev else rt.NA
        pine_tf={'1d':'D','3d':'3D','1w':'W','1M':'M'}.get(self.timeframe)
        if pine_tf is None:pine_tf=str(int(self.timeframe[:-1])*(60 if self.timeframe.endswith('h') else 1))
        self.values.update({'mtfData.currentPrice':client['close'],'mtfData.volumeMA':volume_ma,
            'mtfData.vwapValue':vwap,
            'tf':self.timeframe,'executionEngine':self.parameters.get('executionEngine','SCALP'),'bar_index':self.index,'time':timestamp,'hlc3':typical,
            'barstate.isconfirmed':is_confirmed,'barstate.isnew':is_new,'timeframe.period':pine_tf,'syminfo.tickerid':self.symbol,'lastRegime':self.last_regime})
        self.current_client=dict(client)
    def finish(self):
        for key in HISTORY:
            self.histories.setdefault(key,deque(maxlen=self.capacity)).append(self.values.get(key,self.persistent.get(key,rt.NA)))
        self.last_time=self.current_client['open_time'];self.last_client=self.current_client;self.last_regime=self.values['regimeState']
    def session(self,spec):
        # Binance exchange session timezone is UTC, matching Pine's default.
        date=datetime.fromtimestamp(self.current_client['open_time']/1000,timezone.utc)
        minute=date.hour*60+date.minute;a,b=spec.split('-');start=int(a[:2])*60+int(a[2:]);end=int(b[:2])*60+int(b[2:])
        return self.current_client['open_time'] if (start<=minute<end if start<end else minute>=start or minute<end) else rt.NA
    def daily(self,expression):
        # security(..., "1D", ..., lookahead_off, gaps_off): historical values
        # arrive at the daily close; realtime uses the developing daily context.
        external=getattr(self,'external_daily',None)
        if external is not None:
            offset=1 if expression in ('h1','l1') else 0
            return external[-1-offset][{'h1':'high','l1':'low','o':'open'}[expression]] if len(external)>offset else rt.NA
        if self.timeframe in ('3d','1w','1M'):return rt.NA
        at_close=(self.current_client['close_time']+1)%86400000==0
        offset=0 if self.is_realtime or at_close or self.timeframe in ('1d','3d','1w','1M') else 1
        if expression in ('h1','l1'):offset+=1
        if len(self.daily_bars)<=offset:return rt.NA
        bar=self.daily_bars[-1-offset]
        return bar[{'h1':'high','l1':'low','o':'open'}[expression]]
    def ta(self,name,site,*args):
        if site in self.calls:return self.calls[site]
        state=self.technical.setdefault(site,{})
        if name=='ema':
            from ..features.trend import calculate_ema as calculate
            result=calculate(state,*args)
        elif name in ('sma','wma','highest','lowest'):
            value,length=args;length=int(length);queue=state.setdefault('queue',[])
            if not rt.is_na(value) or name in ('highest','lowest'):queue.append(value)
            state['queue']=queue=queue[-length:];valid=[v for v in queue if not rt.is_na(v)]
            if name in ('highest','lowest'):result=(max(valid) if name=='highest' else min(valid)) if valid else rt.NA
            elif len(valid)<length:result=rt.NA
            elif name=='sma':result=math.fsum(valid)/length
            else:
                from ..features.ema_structure import calculate_wma as calculate
                result=calculate(valid)
        elif name=='rsi':
            from ..features.momentum import calculate_rsi as calculate
            result=calculate(state,*args)
        elif name=='atr':
            from ..features.volatility import calculate
            result=calculate(state,self.current_client,*args)
        elif name=='dmi':
            from ..features.momentum import calculate_dmi
            result=calculate_dmi(state,self.current_client,*args)
        elif name in ('pivothigh','pivotlow'):
            value,left,right=args;left,right=int(left),int(right);queue=state.setdefault('queue',[]);queue.append(value);state['queue']=queue=queue[-(left+right+1):]
            result=rt.NA
            if len(queue)==left+right+1 and not any(rt.is_na(v) for v in queue):
                center=queue[left]
                # Pine selects the rightmost maximum/minimum in a tied window.
                if name=='pivothigh':valid=all(center>=v for v in queue[:left]) and all(center>v for v in queue[left+1:])
                else:valid=all(center<=v for v in queue[:left]) and all(center<v for v in queue[left+1:])
                if valid:result=center
        elif name=='valuewhen':
            condition,value,occurrence=args;queue=state.setdefault('queue',[])
            if rt.truth(condition):queue.append(value)
            state['queue']=queue=queue[-(int(occurrence)+1):];result=queue[-int(occurrence)-1] if len(queue)>occurrence else rt.NA
        else:raise ValueError(f'Unimplemented Pine TA: {name}')
        self.calls[site]=result;return result
