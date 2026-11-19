"""Transfer verified Section 5 history into ADCN.db with lossless compression."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import argparse
from pathlib import Path

from Section_1_Global_Core import data_policy,intelligence_migration
from Section_1_Global_Core.memory_storage.Storage import adcn_store,engine_store


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=engine_store.LEGACY_DB_PATH)
    parser.add_argument('--destination',type=Path,default=adcn_store.DB_PATH)
    parser.add_argument('--source-stopped',action='store_true',help='Confirm source services were stopped before applying')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--until-complete',action='store_true',help='Keep processing bounded, verified batches until finished')
    parser.add_argument('--time-budget',type=float,default=30)
    parser.add_argument('--batch-size',type=int,default=1000)
    args=parser.parse_args(argv)
    if not args.apply:
        print('Preview: source='+str(args.source)+'; destination='+str(args.destination))
        print('Existing ADCN decisions are preserved. Every copied batch is verified; the source is retained.')
        print('Stop source writers, then use --apply --source-stopped. No data changed.')
        return
    if not args.source_stopped:parser.error('--apply requires --source-stopped')
    if not 0<args.time_budget<=60 or not 1<=args.batch_size<=2000:parser.error('Time budget must be >0 and <=60; batch size 1..2000')
    with data_policy.locked(timeout=5):
        intelligence_migration.recover_source(args.source)
        intelligence_migration.run(args.source,args.destination,seconds=args.time_budget,
            until_complete=args.until_complete,batch_size=args.batch_size)


if __name__=='__main__':main()
