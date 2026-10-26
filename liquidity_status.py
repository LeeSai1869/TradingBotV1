"""Read recorder status without network requests: python3 liquidity_status.py BTCUSDT."""
import argparse
import json
from Section_1_Global_Core.liquidity.store import snapshot

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('symbol');args=parser.parse_args()
    report=snapshot(args.symbol.upper(),limit=1);report.pop('history',None)
    print(json.dumps(report,indent=2))
