"""Read-only current audit diagnostics; does not fetch, repair or hash history."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))

import argparse
import json
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Audit import audit_runner


def report(symbol=None):
    pairs=[(s,t) for s in data_policy.active_symbols() if symbol is None or s==symbol.upper() for t in data_policy.active_intervals()]
    manifest=audit_runner.run_fast(sample_rows_per_pair=10,pairs=pairs,persist=False)
    return {'scope':'read-only recent schema/continuity/freshness; source and full history not verified',
            'summary':manifest['summary'],'freshness':manifest['A5'],'recent_continuity':manifest['A2'],
            'historical_downloads':manifest['historical_downloads']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--symbol');args=parser.parse_args()
    print(json.dumps(report(args.symbol),indent=2))


if __name__=='__main__':main()
