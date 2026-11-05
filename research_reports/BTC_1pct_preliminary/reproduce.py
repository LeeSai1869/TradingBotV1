"""One-percent counts from uploaded observed extrema; no new touch times inferred."""
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'research_reports/BTCUSDT_15m_all-history_2pct_pivots_v1.json.gz'

def main():
    data=SOURCE.read_bytes();packet=json.loads(gzip.decompress(data));sides={}
    for side in ('BUY_SIDE','SELL_SIDE'):
        counts=Counter();total=0
        for case in packet['cases']:
            if case['side']!=side:continue
            total+=1;move=case['origin'];maximum=move.get('max_favorable_pct')
            label='HIT' if isinstance(maximum,(int,float)) and math.isfinite(maximum) and maximum>=1.-1e-10 else 'NO_HIT' if move['complete'] else 'CENSORED'
            counts[label]+=1
        resolved=counts['HIT']+counts['NO_HIT']
        sides[side]=dict(pivots=total,counts=dict(counts),resolved=resolved,hit_rate_pct=100*counts['HIT']/resolved if resolved else None)
    result=dict(version='one-percent-extrema-summary-v1',symbol=packet['symbol'],timeframe=packet['timeframe'],
        source_file=SOURCE.name,source_sha256=hashlib.sha256(data).hexdigest(),source_id=packet['source_id'],coverage=packet['coverage'],observed_as_of=packet['observed_as_of'],
        benchmark_pct=1.,source_benchmark_pct=packet['config']['threshold_pct'],horizon='NEXT_OPPOSITE_PIVOT',sides=sides,
        interpretation='Every pivot in uploaded 15m source; LOW=BUY research point, HIGH=SELL research point. Relabeling recorded subsequent-candle maximum favorable excursion at 1%, not recalculating first-touch timestamps, recognition timing, origin-candle recovery, complete feature windows, other timeframes, executed fills or profits. No new candidate entry/exit rule validated. Original 2% report preserved.')
    path=Path(__file__).with_name('summary.json');path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result['sides'],indent=2))

if __name__=='__main__':main()
