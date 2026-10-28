"""Inspect stored candle evidence locally; no exchange calls or database writes."""
import argparse
from datetime import datetime,timezone
import json
from Section_1_Global_Core.global_packet import read_analysis_page,evaluate_price_point


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('symbol');parser.add_argument('--timeframe',default='4h')
    parser.add_argument('--at',required=True,help='ISO timestamp with explicit chart timezone offset, e.g. 2026-10-11T20:00:00+00:00')
    parser.add_argument('--include-point-preview',action='store_true',help='Include a separate unanchored diagnostic; never used by the chart map')
    parser.add_argument('--opportunity-only',action='store_true',help='Compact frozen opportunity map and source diagnostics')
    parser.add_argument('--level',type=float,help='Show closest source-selection records to a price such as 0.1748')
    args=parser.parse_args()
    try:
        point=datetime.fromisoformat(args.at.replace('Z','+00:00'))
        if point.tzinfo is None:raise ValueError('Include a timezone offset')
        stamp=int(point.timestamp()*1000)
    except ValueError as error:parser.error(str(error))
    # A four-day forward cap includes nearby closed candles even on higher frames;
    # the returned score on each row still uses only its own preceding evidence.
    packet=read_analysis_page(args.symbol,args.timeframe,1000,before=stamp+4*86400000,context_history=True)
    bars=packet['bars']
    nearest=sorted(bars,key=lambda b:abs(b['open_time']-stamp))[:5]
    selected=[]
    for row in sorted(nearest,key=lambda b:b['open_time']):
        index=bars.index(row);previous=bars[index-1] if index>0 else None
        inputs={**(previous.get('features') or {}),'close':previous['client']['close']} if previous and previous['client']['close_time']+1==row['open_time'] else None
        reference=row.get('signal_context')
        evidence={'confidence':reference.get('confidence'),'opportunity':reference.get('opportunity')} if reference else {}
        preview=evaluate_price_point(row['client'],row.get('features'),inputs) if args.include_point_preview else None
        selected.append(dict(open_utc=datetime.fromtimestamp(row['open_time']/1000,timezone.utc).isoformat(),
            client=row['client'],decision=row.get('momentum'),confidence=evidence.get('confidence'),
            opportunity=evidence.get('opportunity'),anchor=reference,
            **({'inspection_only_unanchored_preview':preview} if args.include_point_preview else {})))
    if args.opportunity_only or args.level is not None:
        compact=[]
        for row in selected:
            packet=row.get('opportunity') or {};anchor=row.get('anchor') or {}
            audit=packet.get('audit',[])
            if args.level is not None:
                audit=sorted(audit,key=lambda a:min(abs(args.level-a.get('low',args.level)),abs(args.level-a.get('high',args.level))) if not a.get('low',float('inf'))<=args.level<=a.get('high',float('-inf')) else 0)[:12]
            compact.append(dict(open_utc=row['open_utc'],reference_open_time=anchor.get('open_time'),
                reference_side=anchor.get('side'),entry=packet.get('entry'),storage=anchor.get('storage'),inputs=packet.get('inputs'),
                geometry_policy=packet.get('geometry_policy'),areas=packet.get('areas'),source_selection=audit))
        selected=compact
    print(json.dumps(dict(symbol=args.symbol.upper(),timeframe=args.timeframe,requested=args.at,
        note='Stored data only. Scores use candle-close evidence; timestamp matching does not prove this is the referenced chart candle.',
        status='available' if selected else 'No stored candles in this checkout',rows=selected),indent=2,allow_nan=False))

if __name__=='__main__':main()
