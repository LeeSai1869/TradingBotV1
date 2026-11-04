"""Configure bounded feature recovery; no formula changes, state resets or extra worker."""
import argparse
import json
import Section_1_Global_Core.feature_runtime as runtime


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=float);parser.add_argument('--max-bars',type=int)
    parser.add_argument('--priority-symbol');parser.add_argument('--priority-timeframe')
    parser.add_argument('--reset',action='store_true');args=parser.parse_args()
    if bool(args.priority_symbol)!=bool(args.priority_timeframe):parser.error('Set both priority symbol and timeframe')
    if args.reset and any(v is not None for v in (args.seconds,args.max_bars,args.priority_symbol,args.priority_timeframe)):parser.error('Reset cannot be combined with other changes')
    try:
        config=runtime.DEFAULTS.copy() if args.reset else runtime.read()
        if args.seconds is not None:config['time_budget']=args.seconds
        if args.max_bars is not None:config['max_bars']=args.max_bars
        if args.priority_symbol:config['priority']=dict(symbol=args.priority_symbol.upper(),timeframe=args.priority_timeframe)
        changed=args.reset or any(v is not None for v in (args.seconds,args.max_bars,args.priority_symbol))
        if changed:config=runtime.write(config)
        print(json.dumps(config,indent=2))
        print('Scheduling only; existing runner reads settings next maintenance turn. No replay restart.')
    except (OSError,ValueError) as error:parser.exit(1,str(error)+'\n')

if __name__=='__main__':main()
