"""Compare a chronological OHLCV + feature CSV export against the Python engine.

Example: python3 -m Section_4_Features.conversion.validate_export export.csv \
  --symbol ETHUSDT --interval 15m --fields rsi adx ema50

Use the same inputs, timeframe and full history start as Pine. Empty cells are na.
Headers may be Pine contract names or canonical snake_case. No network or DB writes.
"""
import argparse
import csv
import json
import math
from datetime import datetime,timezone
from pathlib import Path
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution.contract import snake,FIELDS
from Section_1_Global_Core.memory_storage.market_data.update_klines import INTERVAL_MS


def timestamp(value):
    try:
        number=float(value);return int(number*1000 if number<100000000000 else number)
    except ValueError:
        date=datetime.fromisoformat(value.replace('Z','+00:00'))
        if date.tzinfo is None:date=date.replace(tzinfo=timezone.utc)
        return int(date.timestamp()*1000)


def compare(path,symbol,interval,fields,parameters=None,absolute=1e-8,relative=1e-8,daily_path=None):
    if any(snake(field) not in FIELDS for field in fields):raise ValueError('Choose fields from the feature contract')
    engine=Engine(symbol,interval,parameters);mismatches=[];rows=0;count=0;daily=[]
    if daily_path:
        with Path(daily_path).open(newline='') as file:
            for row in csv.DictReader(file):daily.append(dict(open_time=timestamp(row['time']),**{k:float(row[k]) for k in ('open','high','low','close','volume')}))
        daily.sort(key=lambda row:row['open_time'])
    with Path(path).open(newline='') as file:
        reader=csv.DictReader(file)
        if reader.fieldnames is None:raise ValueError('CSV needs headers')
        headers={snake(name):name for name in reader.fieldnames}
        required={'time','open','high','low','close','volume',*[snake(f) for f in fields]}
        if required-set(headers):raise ValueError('Missing columns: '+', '.join(sorted(required-set(headers))))
        for row in reader:
            time=timestamp(row[headers['time']])
            if interval=='1M':
                date=datetime.fromtimestamp(time/1000,timezone.utc);end=int(date.replace(year=date.year+(date.month==12),month=date.month%12+1).timestamp()*1000)-1
            else:end=time+INTERVAL_MS[interval]-1
            bar=dict(symbol=symbol,interval=interval,open_time=time,close_time=end,**{name:float(row[headers[name]]) for name in ('open','high','low','close','volume')})
            references=None
            if daily_path:
                from bisect import bisect_right
                end_index=bisect_right([d['open_time']+86400000-1 for d in daily],end)
                references=daily[max(0,end_index-3):end_index]
            result=engine.step(bar,daily_bars=references);rows+=1
            for field in fields:
                name=snake(field);raw=row[headers[name]].strip();actual=result.get(name)
                if raw.lower() in ('','na','nan','null'):expected=None
                elif raw.lower() in ('true','false'):expected=raw.lower()=='true'
                else:
                    try:expected=float(raw)
                    except ValueError:expected=raw
                equal=actual==expected
                if isinstance(actual,(float,int)) and not isinstance(actual,bool) and isinstance(expected,(float,int)) and not isinstance(expected,bool):equal=math.isclose(actual,expected,abs_tol=absolute,rel_tol=relative)
                if not equal:
                    count+=1
                    if len(mismatches)<100:mismatches.append(dict(time=time,field=name,expected=expected,actual=actual))
    if not rows:raise ValueError('CSV has no candle rows')
    return {'rows':rows,'fields':fields,'matches':count==0,'mismatch_count':count,'first_mismatches':mismatches}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv');parser.add_argument('--symbol',required=True);parser.add_argument('--interval',required=True,choices=INTERVAL_MS)
    parser.add_argument('--fields',nargs='+',required=True);parser.add_argument('--parameters',default='{}',help='JSON object with the Pine input values')
    parser.add_argument('--daily-csv',help='Optional complete 1D OHLCV CSV for daily request.security inputs')
    args=parser.parse_args();result=compare(args.csv,args.symbol,args.interval,args.fields,json.loads(args.parameters),daily_path=args.daily_csv)
    print(json.dumps(result,indent=2,allow_nan=False));raise SystemExit(0 if result['matches'] else 1)

if __name__=='__main__':main()
