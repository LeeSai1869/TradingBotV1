"""Reproduce descriptive findings from the two uploaded audits, without market DBs."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import gzip
import json
from pathlib import Path
import statistics
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent


def summarize(packet):
    cases=packet['cases'];result=dict(cohort=packet['cohort'],cases=len(cases),models=packet['models'],engine_history_status=packet['engine_history_status'],evidence_coverage=packet.get('evidence_coverage'),coverage={},sides={})
    for frame in ('15m','4h','1d'):
        for engine in ('REGIME','TREND'):
            usable=[r for r in cases if r['context_at_recognition'][frame][engine].get('classification')]
            result['coverage'][frame+':'+engine]=dict(usable=len(usable),total=len(cases),statuses=dict(Counter(r['context_at_recognition'][frame][engine]['status'] for r in cases)),first_known_utc=datetime.fromtimestamp(min(r['known_time'] for r in usable)/1000,timezone.utc).isoformat() if usable else None)
    for side,role in (('BUY_SIDE','resistance'),('SELL_SIDE','support')):
        rows=[r for r in cases if r['side']==side];status=Counter(r['after_known']['status'] for r in rows);resolved=status['HIT']+status['NO_HIT']
        bands=[a for r in rows for a in (r.get('opportunity') or {}).get('areas',[]) if a['direction']==role and a['layer']==1];touches=Counter(a['outcome']['status'] for a in bands);band_resolved=touches['TOUCHED']+touches['NO_TOUCH']
        median=lambda values:statistics.median(values) if values else None
        result['sides'][side]=dict(cases=len(rows),status=dict(status),resolved=resolved,hit_rate_pct=status['HIT']/resolved*100 if resolved else None,
            confidence_bins=[g for g in packet['summary']['groups'] if g['year']=='ALL' and g['side']==side and g['dimension']=='confidence'],
            confidence_modes=[g for g in packet['summary']['groups'] if g['year']=='ALL' and g['side']==side and g['dimension']=='confidence_mode'],
            median_observed_favorable_pct=median([r['after_known']['max_favorable_pct'] for r in rows if r['after_known'].get('max_favorable_pct') is not None]),
            median_bars_observed=median([r['after_known']['bars_observed'] for r in rows if 'bars_observed' in r['after_known']]),
            first_forward_area=dict(available=len(bands),statuses=dict(touches),resolved=band_resolved,touch_rate_pct=touches['TOUCHED']/band_resolved*100 if band_resolved else None,median_distance_pct=median([a['distance_pct'] for a in bands])))
    return result


def main():
    result={}
    for kind in ('context','saved_decision'):
        path=ROOT/'research_reports'/f'BTCUSDT_15m_{kind}_audit_v1.json.gz'
        with gzip.open(path,'rt') as stream:packet=json.load(stream)
        result[kind]=summarize(packet);del packet
    (OUT/'statistics.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    for ax,(side,stats) in zip(axes,result['saved_decision']['sides'].items()):
        bins=[g for g in stats['confidence_bins'] if g['label'] not in ('UNAVAILABLE_OR_INSUFFICIENT','00–10','10–20','20–30','30–40')]
        ax.bar([g['label'] for g in bins],[g['hit_rate_pct'] or 0 for g in bins],color=['#3578b9' if g['resolved']>=30 else '#aab0b5' for g in bins])
        for i,g in enumerate(bins):ax.text(i,(g['hit_rate_pct'] or 0)+.15,f"n={g['resolved']}",ha='center',fontsize=9)
        ax.axhline(stats['hit_rate_pct'],color='#a23b32',linestyle='--',label='All resolved signals')
        ax.set(title=side+' saved decisions',xlabel='Confidence evidence score /100',ylabel='2% hit rate before next opposite pivot (%)',ylim=(0,10));ax.legend(fontsize=9)
    fig.suptitle('Uploaded historical snapshots — descriptive outcomes, not profit or probability calibration\nBins below 40 remain in statistics.json; grey indicates fewer than 30 resolved cases',fontsize=11)
    fig.tight_layout();fig.savefig(OUT/'saved_confidence_bins.png',dpi=150);plt.close(fig)
    print(json.dumps({k:dict(cases=v['cases'],coverage={key:x['usable'] for key,x in v['coverage'].items()}) for k,v in result.items()},indent=2))

if __name__=='__main__':main()
