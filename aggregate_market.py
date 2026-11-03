"""Inspect saved per-engine multi-timeframe intelligence; never runs classifiers."""
import argparse
from datetime import datetime,timezone
import json
from dataclasses import replace
import Section_1_Global_Core.aggregation_processor as aggregation_processor
import Section_1_Global_Core.data_policy as data_policy
from Section_5_Market_Regime.aggregation_config import AggregationConfig


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine',choices=tuple(aggregation_processor.registry()),default='TREND')
    parser.add_argument('--symbols',nargs='+');parser.add_argument('--intervals',nargs='+')
    parser.add_argument('--as-of',help='UTC ISO time; defaults to current publication availability')
    parser.add_argument('--reconstructed-close',action='store_true',help='Explicit simulation using reconstructed candle-close availability, not real publication times')
    parser.add_argument('--summary',action='store_true')
    args=parser.parse_args()
    try:
        at=None
        if args.as_of:
            date=datetime.fromisoformat(args.as_of.replace('Z','+00:00'));at=int((date if date.tzinfo else date.replace(tzinfo=timezone.utc)).timestamp()*1000)
        cfg=replace(AggregationConfig(),availability='RECONSTRUCTED_CLOSE' if args.reconstructed_close else 'ACTUAL')
        rows=[]
        for symbol in sorted(set(args.symbols or data_policy.active_symbols())):
            row=aggregation_processor.refresh(symbol,args.engine,intervals=args.intervals,config=cfg,as_of=at,force=True)
            rows.append(row)
            if args.summary:
                result=row['latest'];print(symbol,args.engine,result['alignment'],'coverage='+str(result['coverage']),'evidence='+str(result['confidence']),'policy='+result['availability_policy'])
                for tf,value in result['timeframes'].items():
                    if value['active']:print(' ',tf,value['reason'] or value['classification'])
        if not args.summary:print(json.dumps(rows,indent=2,allow_nan=False))
    except (ValueError,TypeError,OSError,RuntimeError) as error:parser.exit(1,str(error)+'\n')

if __name__=='__main__':main()
